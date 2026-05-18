from main.device_gateway import BaseTest


# Weights below are arbitrarily split uniformly between test cases.
# In real world scenarios we can have any combination (up to extremes).


class NoGroup(BaseTest):
    weight = 25


class InWave(BaseTest):
    weight = 25
    group = "test-dspl-group-1"


class NoWaveGroupMismatch(BaseTest):
    weight = 25
    group = "test-dspl-group-9"


class NoWaveTagMismatch(BaseTest):
    weight = 25
    group = "test-dspl-group-1"
    tag = "beta"
