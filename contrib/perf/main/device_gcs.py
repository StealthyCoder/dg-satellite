from tasks.device_gcs import GCSTasks

from users.gcs import GCSUser


class BaseTest(GCSUser):
    abstract = True

    tasks = [
        GCSTasks,
    ]


class Test(BaseTest):
    pass
