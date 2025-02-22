import torch
from torch import nn, Tensor
from typing import Optional, Tuple

from .synth import OscillatorInterface
from .filters import FilterInterface, LTVFilterInterface
from .noise import NoiseInterface
from .utils import TimeContext, linear_upsample


class HarmonicPlusNoiseSynth(nn.Module):
    def __init__(
        self,
        harm_oscillator: OscillatorInterface,
        noise_generator: NoiseInterface,
        harm_filter: Optional[LTVFilterInterface] = None,
        noise_filter: Optional[LTVFilterInterface] = None,
        end_filter: Optional[FilterInterface] = None,
    ):
        super().__init__()

        # Time-varying components
        self.harm_oscillator = harm_oscillator
        self.noise_generator = noise_generator
        self.harm_filter = harm_filter
        self.noise_filter = noise_filter

        # Static components
        self.end_filter = end_filter

    def forward(
        self,
        ctx: TimeContext,
        phase_params: Tuple[Tensor, Optional[Tensor]],
        harm_osc_params: Tuple[Tensor, ...],
        harm_filt_params: Tuple[Tensor, ...],
        noise_filt_params: Tuple[Tensor, ...],
        noise_params: Tuple[Tensor, ...] = (),
    ) -> Tensor:
        """
        Args:
            phase: (batch_size, samples)
        """
        phase, *_ = phase_params
        assert torch.all(phase >= 0) and torch.all(phase <= 0.5)
        upsampled_phase = linear_upsample(phase, ctx)

        if len(_):
            voicing = _[0]
            assert torch.all(voicing >= 0) and torch.all(voicing <= 1)
            upsampled_voicing = linear_upsample(voicing, ctx)
            upsampled_phase = upsampled_phase * upsampled_voicing

        # Time-varying components
        harm_osc = self.harm_oscillator(upsampled_phase, *harm_osc_params, ctx=ctx)
        noise = self.noise_generator(harm_osc, *noise_params, ctx=ctx)
        if self.harm_filter is not None:
            harm_osc = self.harm_filter(harm_osc, *harm_filt_params, ctx=ctx)
        if self.noise_filter is not None:
            noise = self.noise_filter(noise, *noise_filt_params, ctx=ctx)

        out = harm_osc[:, : noise.shape[1]] + noise[:, : harm_osc.shape[1]]

        # Static components
        if self.end_filter is not None:
            return self.end_filter(out)
        else:
            return out
