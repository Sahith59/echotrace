from unittest.mock import Mock, patch

from echotrace.native_adapt import _optimizer_update


def test_optimizer_update_rejects_nonfinite_gradients_before_counting_step():
    scaler = Mock()
    optimizer = Mock()
    scheduler = Mock()
    parameters = [Mock()]

    with patch("echotrace.native_adapt.clip_grad_norm_", side_effect=RuntimeError("nonfinite")) as clip:
        try:
            _optimizer_update(scaler, optimizer, scheduler, parameters)
        except RuntimeError as error:
            assert "nonfinite" in str(error)
        else:
            raise AssertionError("nonfinite gradients must abort training")

    clip.assert_called_once_with(parameters, 1.0, error_if_nonfinite=True)
    scaler.step.assert_not_called()
    scheduler.step.assert_not_called()

