from unittest.mock import Mock, patch

import json

from echotrace.native_adapt import _optimizer_update, main


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


def test_main_prints_compact_result_without_split_provenance(capsys, tmp_path):
    result = {"best_epoch":1,"optimizer_steps":625,"adapted_weights_sha256":"a"*64,
              "elapsed_seconds":42.0,"split_provenance":{"train":[{"file_id":"secret-ish-row"}]}}
    with patch("echotrace.native_adapt.run",return_value=result):
        assert main(["--train",str(tmp_path/"train.csv"),"--selection",str(tmp_path/"selection.csv"),
                     "--dataset-root",str(tmp_path),"--output",str(tmp_path/"out")]) == 0
    printed=json.loads(capsys.readouterr().out)
    assert printed == {"best_epoch":1,"optimizer_steps":625,"adapted_weights_sha256":"a"*64,
                       "elapsed_seconds":42.0}
