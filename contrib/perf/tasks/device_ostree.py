import locust


@locust.tag("ostree")
@locust.tag("ostree:ostree")
class OSTreeTasks(locust.TaskSet):
    @locust.task
    @locust.tag("ostree:ostree:config")
    def ostree_config(self):
        self.client.get("/config", name="ostree:config").raise_for_status()

    @locust.task
    @locust.tag("ostree:ostree:summary")
    def ostree_summary(self):
        self.client.get("/summary", name="ostree:summary").raise_for_status()

    @locust.task
    @locust.tag("ostree:ostree:download-urls")
    def ostree_download_urls(self):
        self.client.post(
            "/download-urls", name="ostree:download-urls"
        ).raise_for_status()


@locust.tag("ostree")
@locust.tag("ostree:ostree")
class OSTreeProxyTasks(locust.TaskSet):
    def on_start(self):
        r = self.client.get("/objects/objects.list", name="ostree:ostree:list")
        r.raise_for_status()
        self._objects = r.text.split("\n")
        self._objects_gen = (obj for obj in self._objects if len(obj) > 0)

        r = self.client.get("/objects/deltas.list", name="ostree:ostree:deltas:list")
        r.raise_for_status()
        self._deltas = r.text.split("\n")
        self._deltas_gen = (d for d in self._deltas if len(d) > 0)

    @locust.task
    @locust.tag("ostree:ostree:objects")
    def ostree_download_objects(self):
        try:
            o = next(self._objects_gen)
        except StopIteration:
            self._objects_gen = (obj for obj in self._objects if len(obj) > 0)
            o = next(self._objects_gen)

        self.client.get(o, name="ostree:ostree:objects").raise_for_status()

    @locust.task
    @locust.tag("ostree:ostree:deltas")
    def ostree_download_deltas(self):
        try:
            d = next(self._deltas_gen)
        except StopIteration:
            self._deltas_gen = (d for d in self._deltas if len(d) > 0)
            d = next(self._deltas_gen)

        self.client.get(
            d, name="ostree:ostree:deltas", allow_redirects=False
        ).raise_for_status()
