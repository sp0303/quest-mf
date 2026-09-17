"""Largest Triangle Three Buckets (LTTB) downsampling algorithm.

Reduces large time-series to <= target_points while preserving visual peaks and troughs.
"""

from __future__ import annotations

import numpy as np


def lttb(
    timestamps: list | np.ndarray,
    values: list[float] | np.ndarray,
    target_points: int = 2000,
) -> tuple[list, list[float]]:
    """Downsample (timestamps, values) using Largest Triangle Three Buckets (LTTB).

    If length <= target_points, returns the input unchanged.
    """
    n = len(values)
    if n <= target_points or target_points < 3:
        return list(timestamps), [float(v) for v in values]

    # Convert to numeric x (index 0..n-1) and y
    y = np.asarray(values, dtype=np.float64)
    x = np.arange(n, dtype=np.float64)

    sampled_indices = [0]
    bucket_size = (n - 2) / (target_points - 2)

    a = 0  # Index of previously selected point

    for i in range(target_points - 2):
        # Current bucket range
        curr_start = int(np.floor((i + 0) * bucket_size)) + 1
        curr_end = int(np.floor((i + 1) * bucket_size)) + 1
        curr_end = min(curr_end, n)

        # Next bucket range (for calculating average point C)
        next_start = int(np.floor((i + 1) * bucket_size)) + 1
        next_end = int(np.floor((i + 2) * bucket_size)) + 1
        next_end = min(next_end, n)

        if next_start < next_end:
            avg_x = np.mean(x[next_start:next_end])
            avg_y = np.mean(y[next_start:next_end])
        else:
            avg_x = x[-1]
            avg_y = y[-1]

        # Point A coordinates
        ax = x[a]
        ay = y[a]

        # Find point in current bucket maximizing triangle area:
        # Area = 0.5 * |(ax - avg_x)(y - ay) - (ax - x)(avg_y - ay)|
        bx = x[curr_start:curr_end]
        by = y[curr_start:curr_end]

        areas = np.abs((ax - avg_x) * (by - ay) - (ax - bx) * (avg_y - ay))
        max_idx = curr_start + int(np.argmax(areas))

        sampled_indices.append(max_idx)
        a = max_idx

    # Always include the last point
    sampled_indices.append(n - 1)

    res_times = [timestamps[idx] for idx in sampled_indices]
    res_vals = [float(values[idx]) for idx in sampled_indices]
    return res_times, res_vals
