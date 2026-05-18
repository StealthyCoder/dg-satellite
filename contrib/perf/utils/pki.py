from cryptography import x509
from cryptography.x509.oid import NameOID  # type: ignore
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
)
from cryptography.hazmat.primitives.asymmetric import ec
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Callable, ClassVar, Dict, Iterable, Tuple

from utils.k8s import get_gateway_keys


@dataclass
class FactoryKeys:
    root_crt_bytes: bytes
    ca_crt_bytes: bytes
    ca_crt: x509.Certificate
    ca_key: ec.EllipticCurvePrivateKey


class DevicePki:
    __cache_lock__: ClassVar[RLock] = RLock()
    __repo_id_cache__: ClassVar[Dict[str, str]]
    __sota_toml_cache__: ClassVar[Dict[str, str]] = {}
    __gateway_keys__: ClassVar[Dict[str, FactoryKeys]] = {}

    ########################
    # Online & Offline PKI #
    ########################

    @staticmethod
    def gen_device_csr(factory: str, uuid: str) -> Tuple[bytes, bytes]:
        pk = ec.generate_private_key(ec.SECP256R1(), default_backend())

        csr = (
            x509.CertificateSigningRequestBuilder()
            .subject_name(
                x509.Name(
                    [
                        x509.NameAttribute(NameOID.COMMON_NAME, uuid),
                        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, factory),
                        # For performance we do only really care about production devices
                        x509.NameAttribute(NameOID.BUSINESS_CATEGORY, "production"),
                    ]
                )
            )
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    content_commitment=False,
                    key_encipherment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    key_cert_sign=False,
                    crl_sign=False,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .add_extension(
                x509.ExtendedKeyUsage([x509.ExtendedKeyUsageOID.CLIENT_AUTH]),
                critical=True,
            )
            .sign(pk, SHA256(), default_backend())
        )

        return (
            pk.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()),  # type: ignore
            csr.public_bytes(Encoding.PEM),
        )

    ###############
    # Offline PKI #
    ###############

    @staticmethod
    def gen_test_device_ca(keys: Dict[str, str]) -> FactoryKeys:
        if "ca_crt" not in keys or "ca_key" not in keys or "ca_pass" not in keys:
            raise RuntimeError("This factory did not configure online device CA")

        crypto = default_backend()
        online_ca_pass = keys["ca_pass"].encode()
        online_ca_key = crypto.load_pem_private_key(
            keys["ca_key"].encode(), online_ca_pass
        )
        online_ca_cert = offline_ca_cert = None
        for pem in _iter_certs(keys["ca_crt"]):
            ca_cert = crypto.load_pem_x509_certificate(pem.encode())
            if (
                ca_cert.public_key().public_numbers()
                == online_ca_key.public_key().public_numbers()
            ):
                online_ca_cert = ca_cert
            else:
                offline_ca_cert = ca_cert
        if online_ca_cert is None:
            raise RuntimeError("This factory did not configure online device CA")
        if offline_ca_cert is None:
            raise RuntimeError("This factory did not configure offline device CA")

        # Generate intermediate CA for test to sign device client certificates
        # A reason why online CA doesn't suite our needs is that it lacks an owner uid in its CN
        # Because of that device-gateway wouldn't allow such devices to auto-register
        inter_pk = ec.generate_private_key(ec.SECP256R1(), default_backend())
        inter_cert = (
            x509.CertificateBuilder()
            .subject_name(offline_ca_cert.subject)
            .serial_number(x509.random_serial_number())
            .issuer_name(online_ca_cert.subject)
            .public_key(inter_pk.public_key())
            .not_valid_before(datetime.now(timezone.utc))
            .not_valid_after(datetime.now(timezone.utc) + timedelta(days=7300))
            .add_extension(
                x509.BasicConstraints(ca=True, path_length=0),
                critical=True,
            )
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    content_commitment=False,
                    key_encipherment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    key_cert_sign=True,
                    crl_sign=False,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .add_extension(
                x509.ExtendedKeyUsage([x509.ExtendedKeyUsageOID.CLIENT_AUTH]),
                critical=True,
            )
            .sign(online_ca_key, SHA256(), crypto)
        )

        return FactoryKeys(
            root_crt_bytes=keys["root_crt"].encode(),
            ca_crt_bytes=inter_cert.public_bytes(Encoding.PEM),
            ca_crt=inter_cert,
            ca_key=inter_pk,
        )

    @staticmethod
    def sign_device_csr_offline(csr: bytes, keys: FactoryKeys) -> bytes:
        crypto = default_backend()
        cert = crypto.load_pem_x509_csr(csr)
        uuid = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value

        device_cert = (
            x509.CertificateBuilder()
            .subject_name(cert.subject)
            .serial_number(int("0x" + uuid, 16))
            .issuer_name(keys.ca_crt.subject)
            .public_key(cert.public_key())
            .not_valid_before(datetime.now(timezone.utc))
            .not_valid_after(datetime.now(timezone.utc) + timedelta(days=7300))
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    content_commitment=False,
                    key_encipherment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    key_cert_sign=False,
                    crl_sign=False,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .add_extension(
                x509.ExtendedKeyUsage([x509.ExtendedKeyUsageOID.CLIENT_AUTH]),
                critical=True,
            )
            .sign(keys.ca_key, SHA256(), crypto)
        )

        return device_cert.public_bytes(encoding=Encoding.PEM)

    @classmethod
    def cache_sota_toml(self, factory: str, sota_toml: str):
        self.__sota_toml_cache__[factory] = sota_toml

    @classmethod
    def get_sota_toml(self, factory: str, updater: Callable):
        toml = self.__sota_toml_cache__.get(factory)
        if toml is None:
            with self.__cache_lock__:
                toml = self.__sota_toml_cache__.get(factory)
                if toml is None:
                    updater()
                    toml = self.__sota_toml_cache__.get(factory)
        return toml

    @classmethod
    def cache_repo_ids(self, repo_ids: Dict[str, str]):
        self.__repo_id_cache__ = repo_ids

    @classmethod
    def get_repo_id(self, factory: str, updater: Callable):
        try:
            kv = self.__repo_id_cache__
        except AttributeError:
            with self.__cache_lock__:
                try:
                    kv = self.__repo_id_cache__
                except AttributeError:
                    updater()
                    kv = self.__repo_id_cache__

        return kv[factory]

    @classmethod
    def get_gateway_keys(self, repo_id: str) -> FactoryKeys:
        keys = self.__gateway_keys__.get(repo_id)
        if keys is None:
            with self.__cache_lock__:
                keys = self.__gateway_keys__.get(repo_id)
                if keys is None:
                    key_data = get_gateway_keys(repo_id, allow_shared=False)
                    self.__gateway_keys__[repo_id] = keys = self.gen_test_device_ca(
                        key_data
                    )
        return keys


def _iter_certs(cert: str) -> Iterable[str]:
    for c in [x for x in cert.split("-----END CERTIFICATE-----") if x and x.strip()]:
        yield c + "-----END CERTIFICATE-----"
