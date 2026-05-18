from tasks.device_ostree import OSTreeTasks, OSTreeProxyTasks

from users.device import DeviceOstreeUser


class BaseTest(DeviceOstreeUser):
    abstract = True

    tasks = [
        OSTreeTasks,
        OSTreeProxyTasks,
    ]


class Test(BaseTest):
    pass
