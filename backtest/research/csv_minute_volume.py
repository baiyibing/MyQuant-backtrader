"""研究用已加载 raw 分钟股数 → 完成桶容量；不读取行情、不做单位转换。"""

from __future__ import annotations

from numbers import Integral, Real

import pandas as pd

from backtest.research.ashare_volume_cap import BucketVolume, VolumeCap, VolumeKey

UNIT = "raw_shares_incremental"


def validate_participation_rate(rate: float | None) -> None:
    if rate is not None:
        # 沿用容量核的 ValueError / 有限 [0,1] 语义，包括显式 0。
        VolumeCap(rate, None)


def completed_minute_volumes(minute_bars) -> dict[VolumeKey, BucketVolume]:
    """调用方声明 volume 为 raw 增量股数；bucket_end 为研究可得时点。

    09:30 竞价和 13:00 开盘行没有完成的一分钟桶，不提供容量。
    未登记 key 由 VolumeCap fail-closed；缺列/坏量/重复桶则在运行前拒绝。
    不认证源时间标签或 publication PIT，也不把旧湖的手数冒充股数。
    """
    samples = {}
    for code, frame in minute_bars.items():
        if not {"ymd", "hm", "volume"} <= set(frame.columns):
            raise ValueError(f"participation_rate requires minute ymd/hm/volume: {code}")
        if frame.duplicated(["ymd", "hm"]).any() or (
            "_tail_duplicate" in frame and frame["_tail_duplicate"].any()
        ):
            raise ValueError(f"duplicate minute volume bucket: {code}")
        for day in frame["ymd"].unique():
            if len(str(day)) != 8 or pd.isna(pd.to_datetime(str(day), format="%Y%m%d", errors="coerce")):
                raise ValueError(f"invalid minute session: {code} {day}")
        for day, hm, quantity in frame[["ymd", "hm", "volume"]].itertuples(index=False, name=None):
            if not isinstance(hm, Integral) or isinstance(hm, bool):
                raise ValueError(f"invalid minute bucket: {code} {day} {hm}")
            day = str(day)
            if isinstance(quantity, bool) or not isinstance(quantity, Real):
                raise ValueError(f"invalid minute shares: {code} {day} {hm}")
            # 浮点股数只接受精确非负整数，且不超出连续可表示整数范围。
            if not isinstance(quantity, Integral):
                if not 0 <= quantity <= 2**53 or quantity != int(quantity):
                    raise ValueError(f"invalid minute shares: {code} {day} {hm}")
            if quantity < 0:
                raise ValueError(f"negative minute shares: {code} {day} {hm}")
            if 571 <= hm <= 690 or 781 <= hm <= 900:
                samples[code, day, int(hm)] = BucketVolume(int(quantity), int(hm), UNIT)
            elif hm not in (570, 780):
                raise ValueError(f"out-of-session minute bucket: {code} {day} {hm}")
    return samples
