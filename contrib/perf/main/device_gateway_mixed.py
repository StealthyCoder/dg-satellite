from main.device_gateway import BaseTest
from utils.shapers import TcNetemShape


# Just an example module.  If we did this scientifically - we'd go for this:
# http://www.unixunique.com/2018/07/linux-network-emulator-custom-delay_9.html
# A good habit is to keep a sum of weights equal to 100 so that they are percents


class Fast(BaseTest):
    weight = 15
    network_shape = TcNetemShape.parse("netem.latency=5ms")


class Slow(BaseTest):
    weight = 5
    network_shape = TcNetemShape.parse(
        "netem.latency=250ms:jitter=100ms:jitter_corr=30:jitter_dist=paretonormal:"
        "rate=360kbps:loss_bernoulli=3:duplicate=2:reorder=5:corrupt=1",
    )


class NormalFiber(BaseTest):
    weight = 30
    network_shape = TcNetemShape.parse(
        "netem.latency=50ms:jitter=20ms:jitter_dist=normal",
    )


# https://patchwork.ozlabs.org/project/netdev/patch/1510175399-7404-4-git-send-email-dave.taht@gmail.com/
class NormalWifi(BaseTest):
    weight = 30
    network_shape = TcNetemShape.parse(
        "netem.latency=20ms:rate=200mbit:overhead=90:limit=512:"
        "slot_delay=5ms:slot_jitter=5ms:slot_dist=pareto:slot_bytes=64k:slot_packets=42"
    )


# http://webpersonal.uma.es/~TORIL/files/2017%20WPC%20QoE%20netem%20testbed.pdf
# https://www.badunetworks.com/9-sets-of-sample-tc-commands-to-simulate-common-network-scenarios/
class NormalLTE(BaseTest):
    weight = 20
    network_shape = TcNetemShape.parse(
        "netem.latency=20ms:rate=100mbit:loss_bernoulli=1:limit=512:"
        "slot_delay=5ms:slot_jitter=300ms:slot_dist=paretonormal"
    )
