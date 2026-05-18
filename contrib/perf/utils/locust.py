from locust.shape import LoadTestShape


class ConstantShape(LoadTestShape):
    """A constant load test shape which ignores a spawn rate"""

    def tick(self):
        targets_users = self.runner.environment.parsed_options.num_users
        return targets_users, targets_users
