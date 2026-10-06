"""Collective control (LOOK) with no central dispatcher."""
from .base import Strategy


class CollectiveLook(Strategy):
    name = "collective"
    label = "Collective (LOOK)"
    description = (
        "Every car answers every hall call. Cars keep moving while there is work "
        "ahead and stop for calls in their travel direction. With several cars "
        "this tends to send more than one car to the same call."
    )
