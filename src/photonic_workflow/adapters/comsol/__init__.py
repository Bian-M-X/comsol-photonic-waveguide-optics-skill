"""COMSOL adapter namespace; native Java batch remains the trusted default route."""

from ..descriptors import EXTERNAL_DESCRIPTOR_BY_NAME

DESCRIPTOR = EXTERNAL_DESCRIPTOR_BY_NAME["comsol-native-java-batch"]
