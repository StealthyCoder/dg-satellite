import locust

from random import randint
from typing import ClassVar, Tuple

from utils.env import DEVICE_CLOSE_CONN
from utils.events import tracking


@locust.tag("gateway")
@locust.tag("gateway:repo")
class GatewayTufRepoTasks(locust.TaskSet):
    @locust.task
    @locust.tag("gateway:repo:root-latest")
    def repo_root_latest(self):
        self._call_tuf("root")

    @locust.task
    @locust.tag("gateway:repo:root")
    def repo_root(self, version=1):
        self._call_tuf(f"{version}.root")

    @locust.task
    @locust.tag("gateway:repo:timestamp")
    def repo_timestamp(self):
        self._call_tuf("timestamp")

    @locust.task
    @locust.tag("gateway:repo:snapshot")
    def repo_snapshot(self):
        self._call_tuf("snapshot")

    @locust.task
    @locust.tag("gateway:repo:targets")
    def repo_targets(self):
        self._call_tuf("targets")

    def _call_tuf(self, role: str):
        self.client.get(
            "/repo/{}.json".format(role),
            name="gateway:repo:{}".format(role),
        ).raise_for_status()


@locust.tag("gateway")
@locust.tag("gateway:info")
class GatewayDeviceInfoTasks(locust.TaskSet):
    @locust.task
    @locust.tag("gateway:info:aktoml")
    def aktoml(self):
        self.client.put(
            "/system_info/config",
            name="gateway:info:aktoml",
            data=self.user.device.sota,
        ).raise_for_status()

    @locust.task
    @locust.tag("gateway:info:hardware")
    def hardware(self):
        self.client.put(
            "/system_info",
            name="gateway:info:hardware",
            json={
                f"key_{i}": f"value {i}" for i in range(randint(5, 200))
            },  # up to 5KB
        ).raise_for_status()

    @locust.task
    @locust.tag("gateway:info:network")
    def network(self):
        self.client.put(
            "/system_info/network",
            name="gateway:info:network",
            json={
                "hostname": "locust-test",
                "local_ipv4": "192.168.1.0",
                "mac": "aa:bb:cc:dd:ee:ff",
            },
        ).raise_for_status()

    @locust.task
    @locust.tag("gateway:info:get")
    def device_info(self):
        self.client.get("/device").raise_for_status()


@locust.tag("gateway")
@locust.tag("gateway:hub")
class GatewayDockerHubTasks(locust.TaskSet):
    @locust.task
    @locust.tag("gateway:hub:creds")
    def hub_creds(self):
        resp = self.client.get("/hub-creds/", name="gateway:hub:creds")
        resp.raise_for_status()
        return resp


@locust.tag("gateway")
@locust.tag("gateway:events")
class GatewayEventsTasks(locust.TaskSet):
    @locust.task
    @locust.tag("gateway:events:notify")
    def notify(self):
        corr_id = hex(randint(1, 0xFFFFFFFF))[2:]
        ecu = self.user.device.uuid
        self.client.post(
            "/events",
            name="gateway:events:notify",
            json=[
                {
                    "id": hex(randint(1, 0xFFFFFFFF))[2:],
                    "deviceTime": "2020-12-20T12:20:42Z",
                    "event": {
                        "correlationId": corr_id,
                        "ecu": ecu,
                        "targetName": "locust-test",
                        "version": "42",
                    },
                    "eventType": {"id": evt, "version": 0},
                }
                for evt in (
                    "EcuDownloadStarted",
                    "EcuDownloadCompleted",
                    "EcuInstallationStarted",
                    "EcuInstallationApplied",
                    "EcuInstallationCompleted",
                )
            ],
        ).raise_for_status()


@locust.tag("gateway")
@locust.tag("gateway:states")
class GatewayStatesTasks(locust.TaskSet):
    @locust.task
    @locust.tag("gateway:states:post")
    def post(self):
        self.client.post(
            "/apps-states",
            name="gateway:states:post",
            json={
                "deviceTime": "2022-09-26T14:17:41Z",
                "ostree": "b514063187d50b498bc514c85d51d846c959cbb867bf1ec3f1534b05766f18c5",
                "apps": {
                    "app-01": {
                        "state": "healthy",
                        "uri": "hub.foundries.io/factory/app-01@sha256:59b080fe42d7c45bc81ea17ab772fc8b3bb5ef0950f74669d069a2e6dc266a24",
                        "services": [
                            {
                                "hash": "e1d31eb6da9212897b65e3a1540b48c28ffed8aaba10957119644cb4735056b5",
                                "health": "healthy",
                                "image": "hub.foundries.io/factory/image-01@sha256:e03d32df200df34b329672f88040b3d3e73c3daec3de13bdc7f1e7ae214079d7",
                                "name": "bar",
                                "state": "running",
                                "status": "Up About a minute",
                            },
                            {
                                "hash": "e1d31eb6da9212897b65e3a1540b48c28ffed8aaba10957119644cb4735056b5",
                                "health": "healthy",
                                "image": "hub.foundries.io/factory/image-02@sha256:e03d32df200df34b329672f88040b3d3e73c3daec3de13bdc7f1e7ae214079d7",
                                "name": "bar",
                                "state": "running",
                                "status": "Up About a minute",
                            },
                        ],
                    },
                    "app-02": {
                        "state": "unhealthy",
                        "uri": "hub.foundries.io/factory/app-02@sha256:59b080fe42d7c45bc81ea17ab772fc8b3bb5ef0950f74669d069a2e6dc266a24",
                        "services": [
                            {
                                "hash": "e1d31eb6da9212897b65e3a1540b48c28ffed8aaba10957119644cb4735056b5",
                                "health": "unhealthy",
                                "image": "hub.foundries.io/factory/image-01@sha256:e03d32df200df34b329672f88040b3d3e73c3daec3de13bdc7f1e7ae214079d7",
                                "name": "bar",
                                "state": "exited",
                                "status": "exited (255)",
                            }
                        ],
                    },
                },
            },
        ).raise_for_status()


@locust.tag("gateway")
@locust.tag("gateway:config")
class GatewayConfigTasks(locust.TaskSet):
    @locust.task(weight=99)
    @locust.tag("gateway:config:get")
    def get_config(self):
        self.client.get("/config", name="gateway:config:get").raise_for_status()

    @locust.task(weight=1)
    @locust.tag("gateway:config:set")
    def set_config(self):
        self.client.patch(
            "/config",
            name="gateway:config:set",
            json={
                "reason": "foo",
                "files": [{"name": "foo", "value": "bar", "unencrypted": True}],
            },
        ).raise_for_status()


@locust.tag("gateway")
@locust.tag("gateway:fiotest")
class GatewayFioTestTasks(locust.TaskSet):
    @locust.task
    @locust.tag("gateway:fiotest:flow")
    def run_fiotest(self):
        # For fiotest we cannot run update without create, only a full flow can be tested
        with tracking(self, "gateway:fiotest"):
            r = self.client.post(
                "/tests", name="gateway:fiotest:create", json={"name": "test-dspl"}
            )
            r.raise_for_status()
            tid = r.text

            with self.user.close_conn():
                self.client.put(
                    f"/tests/{tid}",
                    name="gateway:fiotest:complete",
                    json={
                        "status": "PASSED",
                        "details": "detail x",
                        "results": [
                            {"name": "tr-1", "status": "FAILED"},
                            {
                                "name": "tr-2",
                                "status": "PASSED",
                                "local_ts": 1597802911.1365469,
                                "details": "tr2-detail",
                                "metrics": {"m1": 12, "m2": 42.1},
                            },
                        ],
                        "artifacts": ["console.txt"],
                    },
                ).raise_for_status()


@locust.tag("gateway")
@locust.tag("gateway:repo-flow")
class GatewayTufRepoRootFlowTasks(locust.TaskSet):
    root_version_count: ClassVar[int] = 2

    def __init__(self, parent):
        super().__init__(parent)
        self._repo_tasks = GatewayTufRepoTasks(self)

    @locust.task(weight=9900)
    @locust.tag("gateway:repo-flow:root-check")
    def repo_root_latest(self):
        with tracking(self, *self._gen_opnames("root-check")):
            self._repo_tasks.repo_root(self.root_version_count)
            with self.user.close_conn():
                self._repo_tasks.repo_timestamp()

    @locust.task(weight=99)
    @locust.tag("gateway:repo-flow:targets-update")
    def repo_targets_update(self):
        with tracking(self, *self._gen_opnames("targets-update")):
            self._repo_tasks.repo_root(self.root_version_count)
            self._repo_tasks.repo_timestamp()
            self._repo_tasks.repo_snapshot()
            with self.user.close_conn():
                self._repo_tasks.repo_targets()

    @locust.task(weight=1)
    @locust.tag("gateway:repo-flow:root-update")
    def repo_root_update(self):
        with tracking(self, *self._gen_opnames("root-update")):
            for v in range(1, self.root_version_count + 1):
                self._repo_tasks.repo_root(v)
            self._repo_tasks.repo_timestamp()
            self._repo_tasks.repo_snapshot()
            with self.user.close_conn():
                self._repo_tasks.repo_targets()

    @staticmethod
    def _gen_opnames(opname: str) -> Tuple[str, str]:
        return ("gateway:repo-flow", f"gateway:repo-flow:{opname}")


@locust.tag("gateway")
@locust.tag("gateway:aklite-flow")
class GatewayAkliteFlowTasks(locust.TaskSet):
    def __init__(self, parent):
        super().__init__(parent)
        self._app_state_tasks = GatewayStatesTasks(self)
        self._events_tasks = GatewayEventsTasks(self)
        self._hub_tasks = GatewayDockerHubTasks(self)
        self._info_tasks = GatewayDeviceInfoTasks(self)
        self._repo_tasks = GatewayTufRepoTasks(self)

    @locust.task(weight=99)
    @locust.tag("gateway:aklite-flow:check-and-report")
    def check_and_report(self):
        with tracking(self, *self._gen_opnames("check-and-report")):
            self._repo_tasks.repo_root()
            with self.user.close_conn():
                self._repo_tasks.repo_timestamp()

    @locust.task(weight=1)
    @locust.tag("gateway:aklite-flow:full-cycle")
    def full_cycle(self):
        with tracking(self, *self._gen_opnames("full-cycle")):
            self._info_tasks.aktoml()
            self._app_state_tasks.post()
            self._repo_tasks.repo_root()
            self._repo_tasks.repo_timestamp()
            self._repo_tasks.repo_snapshot()
            self._repo_tasks.repo_targets()
            self._info_tasks.network()
            self._info_tasks.hardware()
            self._hub_tasks.hub_creds()
            # In the future we'd probably add an emulation for an actual download
            self._events_tasks.notify()
            with self.user.close_conn():
                # More often than not we'll have more than 1 events notification during 1 cycle.
                self._events_tasks.notify()

    @staticmethod
    def _gen_opnames(opname: str) -> Tuple[str, str]:
        return ("gateway:aklite-flow", f"gateway:aklite-flow:{opname}")
