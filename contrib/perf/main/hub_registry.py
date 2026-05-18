from tasks.hub_registry import (
    HubAnonymousTasks,
    HubAuthTasks,
    HubRegistryTasks,
    HubTasksFlow,
)
from users.hub import HubUser


class HubTests(HubUser):
    tasks = [HubAnonymousTasks, HubAuthTasks, HubRegistryTasks, HubTasksFlow]
