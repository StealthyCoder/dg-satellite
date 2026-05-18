import locust

from utils.events import tracking


@locust.tag("ostree")
@locust.tag("ostree:gcs")
class GCSTasks(locust.TaskSet):
    @locust.task
    @locust.tag("ostree:gcs:objects")
    def gcs_objects(self):
        with tracking(self.client.user, "ostree:gcs:repo"):
            for obj in self.user.objects:
                if len(obj) > 0:
                    self.client.get(obj, name="ostree:gcs:objects").raise_for_status()

    @locust.task
    @locust.tag("ostree:gcs:deltas")
    def gcs_deltas(self):
        for d in self.user.deltas:
            if len(d) > 0:
                self.client.get(d, name="ostree:gcs:deltas").raise_for_status()
