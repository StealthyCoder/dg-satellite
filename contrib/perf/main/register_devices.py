import locust

from tasks.device_register import DeviceRegisterTasks
from users.api import ApiUser


class Test(ApiUser):
    tasks = [DeviceRegisterTasks]
