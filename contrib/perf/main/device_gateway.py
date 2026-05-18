import locust

from tasks.device_gateway import (
    GatewayTufRepoTasks,
    GatewayDeviceInfoTasks,
    GatewayEventsTasks,
    GatewayStatesTasks,
    GatewayDockerHubTasks,
    GatewayConfigTasks,
    GatewayFioTestTasks,
    GatewayTufRepoRootFlowTasks,
    GatewayAkliteFlowTasks,
)
from users.device import DeviceUser


# This allows to import it in other locust files
class BaseTest(DeviceUser):
    abstract = True
    tasks = [
        GatewayTufRepoTasks,
        GatewayDeviceInfoTasks,
        GatewayEventsTasks,
        GatewayStatesTasks,
        GatewayDockerHubTasks,
        GatewayConfigTasks,
        GatewayFioTestTasks,
        GatewayTufRepoRootFlowTasks,
        GatewayAkliteFlowTasks,
    ]


class Test(BaseTest):
    pass
