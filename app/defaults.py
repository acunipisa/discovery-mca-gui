from app.models import MCAConfig


SAMPLE_RATE_HZ = 6.25e6
BUFFER_SIZE = 512
INPUT_RANGE_V = 5.0
OFFSET_V = 0.0
TRIGGER_CHANNEL = 0
HV_CHANNEL = 0
TEST_PULSE_CHANNEL = 1
HOLDOFF_S = 1e-5

TRIGGER_INDEX_ESTIMATE = BUFFER_SIZE // 2
BASELINE_WIDTH = BUFFER_SIZE // 8
BASELINE_CENTER_OFFSET = BUFFER_SIZE // 4


def build_default_mca_config() -> MCAConfig:
    return MCAConfig(
        n_channels=1024,
        voltage_min=0.0,
        voltage_max=5.0,
        baseline_width=BASELINE_WIDTH,
        baseline_center_offset=BASELINE_CENTER_OFFSET,
        trigger_index_estimate=TRIGGER_INDEX_ESTIMATE,
    )
