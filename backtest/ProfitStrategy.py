# ProfitStrategy.py
"""
策略模块：实现五种交易策略的参数化适配
采用策略模式 + 配置预设 + 自定义参数覆盖的增强架构
包含五种预设策略：
- 策略1：亏损2%止损 + 回撤达到利润50%止盈
- 策略2：亏损2%止损 + 动态止盈（持仓天数调整回撤比例）
- 策略3：亏损4%止损 + 盈利20%止盈，并处理开盘10分钟内涨停的特殊保留逻辑
- 策略4：十日线上买进 + 五日线下卖出（纯均线策略）
- 策略5：无止损 + 盈利2%止盈 + 固定时间强制卖出

**与实盘对齐**：CSV / 实盘的卖侧预设权威实现在 ``trade_decision.presets``（``version1``–``version5``）
及 ``trade_decision.wiring``；本模块保留回测与实验入口。阈值或分支逻辑变更时须同步
``tests/test_profit_strategy_trade_decision_preset_parity.py``（与 presets 对照），避免双实现漂移。

**已知语义差**：（1）Strategy3 在「开盘窗口外仍涨停且已达 profit_target」时可能继续保留，presets 会先按 profit_target 卖出（见该测试文件注释）。
（2）Strategy5 仅识别 ``force_sell_policy`` 字面量 ``and``/``or`` 的简写；``force_sell_mode`` 由 ``trade_decision.presets`` 在缺省
``force_sell_policy`` 时解析，回测类不读 ``force_sell_mode``。
"""

from abc import ABC, abstractmethod
import logging
from typing import Tuple, Dict, Optional

logger = logging.getLogger(__name__)


class ProfitStrategy(ABC):
    """策略基类 - 定义统一接口"""

    def __init__(self, **params):
        """
        初始化策略参数
        :param params: 策略专属参数字典
        """
        self.params = params
        self._validate_params()

    def _validate_params(self):
        """子类可重写进行参数校验"""
        pass

    @abstractmethod
    def should_sell(
        self,
        status,
        current_datetime,
        current_price: float,
        is_limit_up: bool,
        is_limit_down: bool,
        indicators: Optional[Dict] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        判断是否应卖出持仓
        :param status: StockStatus对象（含cost_price, holding_high, hold_days等）
        :param current_datetime: 当前时间
        :param current_price: 当前价格
        :param is_limit_up: 当前是否涨停
        :param is_limit_down: 当前是否跌停
        :param indicators: 技术指标字典（含ma5, ma10等）
        :return: (是否卖出, 原因描述)
        """
        pass

    @abstractmethod
    def should_buy(
        self,
        status,
        current_datetime,
        current_price: float,
        is_limit_up: bool,
        is_limit_down: bool,
        indicators: Optional[Dict] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        判断是否应买入股票
        :param status: StockStatus对象
        :param current_datetime: 当前时间
        :param current_price: 当前价格
        :param is_limit_up: 当前是否涨停
        :param is_limit_down: 当前是否跌停
        :param indicators: 技术指标字典
        :return: (是否买入, 原因描述)
        """
        pass

    @staticmethod
    def _calculate_drawdown_ratio(high: float, current: float, cost: float) -> float:
        """
        计算从最高点回撤占盈利部分的比例
        :param high: 持仓期间最高价
        :param current: 当前价格
        :param cost: 成本价
        :return: 回撤比例 (0.0 ～ 1.0+)
        """
        if high <= cost or high <= 0:
            return 0.0
        # 最大盈利金额
        profit_amount = high - cost
        if profit_amount <= 0:
            return 0.0
        # 从高点回撤的金额
        drawdown_amount = max(0.0, high - current)
        # 回撤占盈利的比例
        return drawdown_amount / profit_amount


class Strategy1(ProfitStrategy):
    """策略1: 亏损2%止损 + 回撤达到利润50%止盈"""

    def _validate_params(self):
        self.params.setdefault("stop_loss_pct", 0.02)
        self.params.setdefault("profit_drawdown_pct", 0.50)
        assert 0 < self.params["stop_loss_pct"] < 1, "止损比例需在(0,1)"
        assert 0 < self.params["profit_drawdown_pct"] <= 1, "回撤比例需在(0,1]"

    def should_sell(
        self,
        status,
        current_datetime,
        current_price,
        is_limit_up=False,
        is_limit_down=False,
        indicators=None,
    ):
        if status.cost_price <= 0:
            return False, None

        # 止损判断
        if current_price < status.cost_price:
            loss_ratio = (status.cost_price - current_price) / status.cost_price
            if loss_ratio >= self.params["stop_loss_pct"]:
                return True, f"stop_loss 亏损{loss_ratio * 100:.2f}%"
            return False, None

        # 止盈判断（回撤逻辑）
        if status.holding_high > status.cost_price and status.holding_high > 0:
            drawdown_ratio = self._calculate_drawdown_ratio(
                status.holding_high, current_price, status.cost_price
            )
            if drawdown_ratio >= self.params["profit_drawdown_pct"]:
                # 修改：止盈原因以 profit_take:drawdown 开头，便于上层识别为动态回撤止盈
                return True, f"profit_take:drawdown 回撤{drawdown_ratio * 100:.2f}%"

        return False, None

    def should_buy(
        self,
        status,
        current_datetime,
        current_price,
        is_limit_up=False,
        is_limit_down=False,
        indicators=None,
    ):
        # 买入逻辑由外部选股池控制，策略层允许买入
        return True, "策略1允许买入"


class Strategy2(ProfitStrategy):
    """策略2: 亏损2%止损 + 动态止盈（持仓天数调整回撤比例）"""

    DEFAULT_RULES = {1: 0.50, 2: 0.40, 3: 0.30, 4: 0.20, 5: 0.10}

    def _validate_params(self):
        self.params.setdefault("stop_loss_pct", 0.02)
        self.params.setdefault("dynamic_drawdown_rules", self.DEFAULT_RULES.copy())
        assert 0 < self.params["stop_loss_pct"] < 1, "止损比例需在(0,1)"
        assert isinstance(self.params["dynamic_drawdown_rules"], dict), (
            "动态规则需为字典"
        )

    def should_sell(
        self,
        status,
        current_datetime,
        current_price,
        is_limit_up=False,
        is_limit_down=False,
        indicators=None,
    ):
        if status.cost_price <= 0:
            return False, None

        # 止损判断
        if current_price < status.cost_price:
            loss_ratio = (status.cost_price - current_price) / status.cost_price
            if loss_ratio >= self.params["stop_loss_pct"]:
                return True, f"stop_loss 亏损{loss_ratio * 100:.2f}%"
            return False, None

        # 动态止盈判断
        hold_days = max(1, status.hold_days)  # 至少1天
        # 根据持仓天数获取对应的回撤阈值：优先使用精确天数，否则取最大天数对应的规则，最后默认0.10
        rules = self.params["dynamic_drawdown_rules"]
        threshold = rules.get(hold_days, rules.get(max(rules.keys()), 0.10))

        if status.holding_high > status.cost_price and status.holding_high > 0:
            drawdown_ratio = self._calculate_drawdown_ratio(
                status.holding_high, current_price, status.cost_price
            )
            # 当回撤超过阈值时卖出
            if drawdown_ratio >= threshold:
                profit_pct = (
                    (current_price - status.cost_price) / status.cost_price * 100
                )
                # 修改：止盈原因以 profit_take:drawdown 开头，便于上层识别为动态回撤止盈
                return (
                    True,
                    f"profit_take:drawdown 盈利{profit_pct:.2f}%,持仓{hold_days}天回撤{drawdown_ratio * 100:.2f}%",
                )

        return False, None

    def should_buy(
        self,
        status,
        current_datetime,
        current_price,
        is_limit_up=False,
        is_limit_down=False,
        indicators=None,
    ):
        return True, "策略2允许买入"


class Strategy3(ProfitStrategy):
    """
    策略3: 亏损4%止损 + 盈利20%止盈
    附加特殊规则：开盘后10分钟内（9:30-9:40）若涨停则标记保留，
                 10分钟后若开板则立即卖出（即使未达目标止盈），
                 若继续涨停则持续持有（直到开板或触发目标止盈）。
    """

    def _validate_params(self):
        # 参数必须通过构造传入，此处仅校验有效性
        assert 0 < self.params["stop_loss_pct"] < 1, "止损比例需在(0,1)"
        assert 0 < self.params["profit_target_pct"] <= 1, "止盈比例需在(0,1]"

    def should_sell(
        self,
        status,
        current_datetime,
        current_price,
        is_limit_up=False,
        is_limit_down=False,
        indicators=None,
    ):
        if status.cost_price <= 0:
            return False, None

        # 止损判断
        if current_price < status.cost_price:
            loss_ratio = (status.cost_price - current_price) / status.cost_price
            if loss_ratio >= self.params["stop_loss_pct"]:
                return True, f"stop_loss 亏损{loss_ratio * 100:.2f}%"
            return False, None
        else:
            # 目标止盈判断前，先处理开盘10分钟内的涨停保留逻辑
            current_date = current_datetime.date()
            current_time = current_datetime.time()
            if current_time.hour == 9 and 30 <= current_time.minute < 40:
                # 开盘10分钟内涨停，标记为特殊状态_reserved_for_limit_up，用于10分钟后判断是否开板
                if is_limit_up:
                    if not hasattr(status, "_reserved_for_limit_up"):
                        status._reserved_for_limit_up = True
                        logger.debug(
                            f"{status.stock_code} 开盘10分钟内涨停，保留观察{current_date} {current_time}"
                        )
                        return False, "开盘10分钟内涨停，保留观察"
                    else:
                        status._reserved_for_limit_up = True
                        logger.debug(
                            f"{status.stock_code} 开盘10分钟内涨停，保留观察{current_date} {current_time}"
                        )
                        return False, "开盘10分钟内涨停，保留观察"
                else:
                    # 如果在10分钟内但未涨停，清除之前可能存在的保留标记（例如前一交易日涨停延续到今日开盘）
                    if hasattr(status, "_reserved_for_limit_up"):
                        logger.debug(
                            f"{status.stock_code} 在10分钟内但未涨停，清除保留标记{current_date} {current_time} {status._reserved_for_limit_up}"
                        )
                        delattr(status, "_reserved_for_limit_up")
                    # 非涨停场景不应屏蔽目标止盈：开盘窗口内仍允许达到目标即卖出
                    profit_ratio = (
                        current_price - status.cost_price
                    ) / status.cost_price
                    if profit_ratio >= self.params["profit_target_pct"]:
                        return (
                            True,
                            f"profit_take:target 盈利{profit_ratio * 100:.2f}%达到目标{self.params['profit_target_pct'] * 100:.0f}%",
                        )
            else:
                profit_ratio = (current_price - status.cost_price) / status.cost_price
                # 开盘10分钟后，检查是否开板
                if (
                    hasattr(status, "_reserved_for_limit_up")
                    and status._reserved_for_limit_up
                ):
                    if is_limit_up:
                        # 仍然涨停，继续保留
                        return False, "仍然涨停，继续保留"
                    else:
                        # 开板了，卖出（此信号不作为止盈，保持原字符串，不以 profit_take 开头）
                        delattr(status, "_reserved_for_limit_up")
                        return (
                            True,
                            f"开盘10分钟后开板，卖出，盈利{profit_ratio * 100:.2f}%",
                        )

                # 若无保留标记，则判断是否达到目标盈利（20%）
                if profit_ratio >= self.params["profit_target_pct"]:
                    # 修改：目标止盈原因以 profit_take:target 开头，便于上层识别为静态目标止盈
                    return (
                        True,
                        f"profit_take:target 盈利{profit_ratio * 100:.2f}%达到目标{self.params['profit_target_pct'] * 100:.0f}%",
                    )

        return False, None

    def should_buy(
        self,
        status,
        current_datetime,
        current_price,
        is_limit_up=False,
        is_limit_down=False,
        indicators=None,
    ):
        return True, "策略3允许买入"


class Strategy4(ProfitStrategy):
    """策略4: 十日线上买进 + 五日线下卖出（纯均线策略）"""

    def _validate_params(self):
        # 策略4不使用止损/止盈参数，但保留扩展性
        self.params.setdefault("ma_buy_period", 10)
        self.params.setdefault("ma_sell_period", 5)

    def should_sell(
        self,
        status,
        current_datetime,
        current_price,
        is_limit_up=False,
        is_limit_down=False,
        indicators=None,
    ):
        if not indicators or status.cost_price <= 0:
            return False, None

        # 仅依赖均线信号：价格跌破指定卖出均线时卖出
        ma_sell = indicators.get(f"ma{self.params['ma_sell_period']}")
        if ma_sell is not None and not (isinstance(ma_sell, float) and ma_sell > 0):
            return False, None

        if current_price < ma_sell:
            return (
                True,
                f"ma_signal 价格{current_price:.2f}跌破MA{self.params['ma_sell_period']}({ma_sell:.2f})",
            )

        return False, None

    def should_buy(
        self,
        status,
        current_datetime,
        current_price,
        is_limit_up=False,
        is_limit_down=False,
        indicators=None,
    ):
        if not indicators:
            return False, "指标数据不足"

        # 仅依赖均线信号：价格站上指定买入均线时买入
        ma_buy = indicators.get(f"ma{self.params['ma_buy_period']}")
        if ma_buy is None or not (isinstance(ma_buy, float) and ma_buy > 0):
            return False, "MA指标无效"

        if current_price >= ma_buy:
            return (
                True,
                f"ma_signal 价格{current_price:.2f}站上MA{self.params['ma_buy_period']}({ma_buy:.2f})",
            )

        return False, None


class Strategy5(ProfitStrategy):
    """策略5: 无止损 + 盈利2%止盈 + 固定时间强制卖出（默认）"""

    def _validate_params(self):
        assert 0 < self.params["profit_target_pct"] <= 1, "止盈比例需在(0,1]"
        self.params.setdefault("force_sell_days", 0)
        self.params.setdefault("force_sell_time", "14:50")
        self.params.setdefault("force_sell_policy", "time_only")
        self.params.setdefault("limit_up_reserve_enabled", False)
        self.params.setdefault("limit_up_reserve_start", "09:30")
        self.params.setdefault("limit_up_reserve_end", "09:40")
        assert int(self.params["force_sell_days"]) >= 0, "force_sell_days 需 >=0"

    @staticmethod
    def _parse_force_sell_time(raw, default_time: str = "14:50"):
        val = str(raw or default_time).strip()
        try:
            from datetime import time as _time

            return _time.fromisoformat(val)
        except ValueError:
            from datetime import time as _time

            return _time.fromisoformat(default_time)

    @staticmethod
    def _parse_bool(raw, default: bool = False) -> bool:
        if raw is None:
            return bool(default)
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, (int, float)):
            return raw != 0
        val = str(raw).strip().lower()
        if val in {"1", "true", "yes", "y", "on"}:
            return True
        if val in {"0", "false", "no", "n", "off"}:
            return False
        return bool(default)

    def should_sell(
        self,
        status,
        current_datetime,
        current_price,
        is_limit_up=False,
        is_limit_down=False,
        indicators=None,
    ):
        if status.cost_price <= 0:
            return False, None

        pnl = (current_price - status.cost_price) / status.cost_price
        force_sell_days = int(self.params.get("force_sell_days", 0))
        force_sell_time = self._parse_force_sell_time(
            self.params.get("force_sell_time", "14:50")
        )
        force_sell_policy = (
            str(self.params.get("force_sell_policy", "time_only") or "time_only")
            .strip()
            .lower()
        )
        if force_sell_policy == "and":
            force_sell_policy = "days_and_time"
        elif force_sell_policy == "or":
            force_sell_policy = "days_or_time"
        if force_sell_policy not in {"time_only", "days_or_time", "days_and_time"}:
            force_sell_policy = "time_only"

        reserve_enabled = self._parse_bool(
            self.params.get("limit_up_reserve_enabled", False), default=False
        )
        reserve_start = self._parse_force_sell_time(
            self.params.get("limit_up_reserve_start", "09:30"), default_time="09:30"
        )
        reserve_end = self._parse_force_sell_time(
            self.params.get("limit_up_reserve_end", "09:40"), default_time="09:40"
        )
        now_t = current_datetime.time()
        in_reserve_window = reserve_start <= now_t < reserve_end
        if reserve_enabled:
            if in_reserve_window and is_limit_up:
                status._reserved_for_limit_up = True
                return False, "开盘窗口涨停保留"
            if (
                in_reserve_window
                and hasattr(status, "_reserved_for_limit_up")
                and not is_limit_up
            ):
                delattr(status, "_reserved_for_limit_up")
                return False, None
            if (
                hasattr(status, "_reserved_for_limit_up")
                and status._reserved_for_limit_up
                and not is_limit_up
            ):
                delattr(status, "_reserved_for_limit_up")
                return True, f"开板卖出 盈利{pnl * 100:.2f}%"
        elif hasattr(status, "_reserved_for_limit_up"):
            delattr(status, "_reserved_for_limit_up")

        days_triggered = force_sell_days > 0 and status.hold_days >= force_sell_days
        time_triggered = now_t >= force_sell_time
        if force_sell_policy == "days_and_time":
            force_triggered = days_triggered and time_triggered
        elif force_sell_policy == "days_or_time":
            force_triggered = days_triggered or time_triggered
        else:
            force_triggered = time_triggered
        if force_triggered:
            if force_sell_policy == "days_and_time":
                return (
                    True,
                    f"force_sell days_and_time 持仓{status.hold_days}天 {now_t}",
                )
            if (
                force_sell_policy == "days_or_time"
                and days_triggered
                and not time_triggered
            ):
                return True, f"force_sell days 持仓{status.hold_days}天"
            return True, f"force_sell time {now_t}"

        if pnl >= self.params["profit_target_pct"]:
            return True, f"profit_take:target 盈利{pnl * 100:.2f}%"

        return False, None

    def should_buy(
        self,
        status,
        current_datetime,
        current_price,
        is_limit_up=False,
        is_limit_down=False,
        indicators=None,
    ):
        return True, "策略5允许买入"


class Strategy6(ProfitStrategy):
    """
    策略6：6% 盘中止损 + 基础止盈 1% 锚定的分档回撤止盈。

    止损：市价较买入价回撤 >= stop_loss_pct（默认 6%），盘中触发即按该止损卖。

    止盈（+1% 锚定回撤，分档按持仓交易日数 T+N）：
      记 peak_excess = 持仓期最高价/买入价 - (1 + profit_base_pct)，
          cur_excess  = 市价/买入价 - (1 + profit_base_pct)。
      持仓期最高价从 T+1 起算（T+0 固定为买入价）。
      仅当峰值超过 +1%（peak_excess > 0）且触发价 ≥ 买入价才止盈：
          T+1 档 0.30；T+2 档 0.40；T+3 档 0.50；T+4 档 0.60；T+5+ 档 0.70
          （cur_excess <= 档位 × peak_excess；跌破 +1% 锚但未跌破成本同样触发）。
      开盘 < 买入价×1.01：先观察，市价涨过锚后再按档；开盘 ≥ 锚则当日起按档。
      分钟引擎：触发止盈的 bar 与创新高 bar 间隔不能 < 15 分钟（=15 允许）。
      未过 +1% 锚不止盈（不做正利润回撤）。

    买侧契约（由 RollingInvestmentStrategy / CSV 引擎执行）：
      尾盘涨停当日不买；T+1 09:45 市价>当日开盘则追买，否则弃买。
    """

    PEAK_GAP_MIN = 15

    def __init__(
        self,
        stop_loss_pct: float = 0.06,
        profit_base_pct: float = 0.01,
        trailing_rules: Optional[Dict] = None,
        trailing_default: float = 0.70,
        positive_trail_ratio: float = 0.50,
    ):
        params = {
            "stop_loss_pct": float(stop_loss_pct),
            "profit_base_pct": float(profit_base_pct),
            "trailing_rules": dict(
                trailing_rules or {1: 0.30, 2: 0.40, 3: 0.50, 4: 0.60}
            ),
            "trailing_default": float(trailing_default),
            "positive_trail_ratio": float(positive_trail_ratio),
        }
        super().__init__(**params)

    def _validate_params(self):
        assert 0 < self.params["stop_loss_pct"] < 1, "止损比例需在(0,1)"
        assert 0 < self.params["profit_base_pct"] < 1, "基础止盈锚点需在(0,1)"
        assert 0 < self.params["trailing_default"] <= 1, "T+5+ 回撤档位需在(0,1]"
        assert 0 < self.params["positive_trail_ratio"] <= 1, "正利润回撤比例需在(0,1]"
        for day, ratio in self.params["trailing_rules"].items():
            assert int(day) >= 1, "回撤档位键为持仓交易日数(>=1)"
            assert 0 < ratio <= 1, "回撤档位比例需在(0,1]"

    def should_sell(
        self,
        status,
        current_datetime,
        current_price,
        is_limit_up=False,
        is_limit_down=False,
        indicators=None,
    ):
        cost = float(getattr(status, "cost_price", 0.0) or 0.0)
        if cost <= 0 or current_price <= 0:
            return False, None

        ret = current_price / cost - 1.0
        # 一、止损：6% 盘中触发即卖
        if ret <= -self.params["stop_loss_pct"]:
            return (
                True,
                f"stop_loss 亏损{(-ret) * 100:.2f}%触发{self.params['stop_loss_pct'] * 100:.0f}%止损",
            )

        # 触发价 < 买入价不执行止盈（亏损交给止损）
        if current_price < cost:
            return False, None

        peak_ret = (
            float(getattr(status, "holding_high", current_price) or current_price)
            / cost
            - 1.0
        )
        day = max(1, int(getattr(status, "hold_days", 1) or 1))
        base = self.params["profit_base_pct"]
        peak_excess = peak_ret - base

        if peak_excess > 0:
            peak_tm = None
            if isinstance(indicators, dict):
                peak_tm = indicators.get("peak_time")
            if peak_tm is not None and current_datetime is not None:
                delta_min = (current_datetime - peak_tm).total_seconds() / 60.0
                if 0 <= delta_min < float(self.PEAK_GAP_MIN):
                    return False, None
            ratio = float(
                self.params["trailing_rules"].get(day, self.params["trailing_default"])
            )
            cur_excess = ret - base
            if cur_excess <= ratio * peak_excess:
                return True, (
                    f"profit_take:drawdown 基础止盈上方回撤 "
                    f"T+{day}档{ratio * 100:.0f}%（峰值超额{(peak_excess) * 100:.2f}%，"
                    f"当前超额{(cur_excess) * 100:.2f}%）"
                )

        return False, None

    def should_buy(
        self,
        status,
        current_datetime,
        current_price,
        is_limit_up=False,
        is_limit_down=False,
        indicators=None,
    ):
        return True, "策略6允许买入（买侧涨停拦截由滚动层 skip_limit_up 强制）"


class Strategy8(ProfitStrategy):
    """
    策略8：金榕元交易回测。15% 止损 + 基础止盈 20% 的绝对涨幅分档回撤。

    止损：市价较买入价回撤 >= 15 个点（默认 15%），盘中触发即按该止损卖。

    止盈（峰值涨幅 = 持仓最高价/买入价 - 1；峰值从 T+1 起算）：
      未过基础 20% 不止盈。过锚后回撤到对应绝对涨幅：
          20% < 涨幅 <= 40% → 回撤到 +20%
          40% < 涨幅 <= 60% → 回撤到 +30%
          60% < 涨幅 <= 80% → 回撤到 +50%
          80% < 涨幅 <= 100% → 回撤到 +70%
          100% < 涨幅 <= 120% → 回撤到 +90%
          120% < 涨幅 → 回撤到 +110%
      另：峰值涨幅 > 50% 且现价 <= 最高价 × 80%（最高价回撤 20%）也止盈。
      打到 +20% 当日不硬止盈；须峰值超过 20% 后再回撤到档位。

    买侧契约（由 RollingInvestmentStrategy / CSV 引擎执行）：
      尾盘涨停当日不买；T+1 09:45 市价>当日开盘则追买，否则弃买。
    """

    def __init__(self, stop_loss_pct: float = 0.15):
        super().__init__(stop_loss_pct=float(stop_loss_pct))

    def _validate_params(self):
        assert 0 < self.params["stop_loss_pct"] < 1, "止损比例需在(0,1)"

    def should_sell(
        self,
        status,
        current_datetime,
        current_price,
        is_limit_up=False,
        is_limit_down=False,
        indicators=None,
    ):
        from backtest.research.strategy8_rules import (
            stop_hits,
            take_profit_reason,
        )

        del current_datetime, is_limit_up, is_limit_down, indicators
        cost = float(getattr(status, "cost_price", 0.0) or 0.0)
        if cost <= 0 or current_price <= 0:
            return False, None
        if stop_hits(current_price, cost, self.params["stop_loss_pct"]):
            ret = current_price / cost - 1.0
            return (
                True,
                f"stop_loss 亏损{(-ret) * 100:.2f}%触发"
                f"{self.params['stop_loss_pct'] * 100:.0f}%止损",
            )
        peak = float(
            getattr(status, "holding_high", current_price) or current_price
        )
        reason = take_profit_reason(current_price, cost, peak)
        if reason:
            return True, f"profit_take:{reason}"
        return False, None

    def should_buy(
        self,
        status,
        current_datetime,
        current_price,
        is_limit_up=False,
        is_limit_down=False,
        indicators=None,
    ):
        return True, "策略8允许买入（买侧涨停拦截由滚动层 skip_limit_up 强制）"


class StrategyFactory:
    """策略工厂：预设配置 + 自定义参数覆盖"""

    # 预设策略配置（策略类, 默认参数字典）
    PRESETS = {
        "version1": (Strategy1, {"stop_loss_pct": 0.02, "profit_drawdown_pct": 0.50}),
        "version2": (
            Strategy2,
            {
                "stop_loss_pct": 0.02,
                "dynamic_drawdown_rules": {1: 0.50, 2: 0.40, 3: 0.30, 4: 0.20, 5: 0.10},
            },
        ),
        "version3": (Strategy3, {"stop_loss_pct": 0.04, "profit_target_pct": 0.20}),
        "version4": (Strategy4, {"ma_buy_period": 10, "ma_sell_period": 5}),
        "version5": (
            Strategy5,
            {
                "profit_target_pct": 0.02,
                "force_sell_time": "14:50",
                "force_sell_policy": "time_only",
                "force_sell_days": 0,
                "limit_up_reserve_enabled": False,
                "limit_up_reserve_start": "09:30",
                "limit_up_reserve_end": "09:40",
            },
        ),
        "version6": (
            Strategy6,
            {
                "stop_loss_pct": 0.06,
                "profit_base_pct": 0.01,
                "trailing_rules": {1: 0.30, 2: 0.40, 3: 0.50, 4: 0.60},
                "trailing_default": 0.70,
                "positive_trail_ratio": 0.50,
            },
        ),
        "version8": (Strategy8, {"stop_loss_pct": 0.15}),
    }

    @classmethod
    def create(
        cls, version: str, custom_params: Optional[Dict] = None
    ) -> ProfitStrategy:
        """
        创建策略实例
        :param version: 策略版本标识 (version1 ～ version5)
        :param custom_params: 自定义参数覆盖预设
        :return: 策略实例
        :raises ValueError: 无效的策略版本
        """
        if version not in cls.PRESETS:
            valid_versions = ", ".join(cls.PRESETS.keys())
            raise ValueError(f"无效策略版本: {version}。有效版本: {valid_versions}")

        strategy_cls, default_params = cls.PRESETS[version]
        params = {**default_params, **(custom_params or {})}

        try:
            strategy = strategy_cls(**params)
            logger.info(f"创建策略实例: {version} | 参数: {params}")
            return strategy
        except Exception as e:
            logger.error(f"创建策略 {version} 失败: {e}", exc_info=True)
            raise


# ==================== 使用示例（文档用途） ====================
if __name__ == "__main__":
    # 示例1: 使用预设策略
    strategy_v1 = StrategyFactory.create("version1")

    # 示例2: 微调参数（将策略1的回撤阈值改为60%）
    strategy_v1_custom = StrategyFactory.create(
        "version1", custom_params={"profit_drawdown_pct": 0.60}
    )

    # 示例3: 完全自定义策略2的动态规则
    custom_rules = {1: 0.55, 2: 0.45, 3: 0.35, 4: 0.25, 5: 0.15, 6: 0.10}
    strategy_v2_custom = StrategyFactory.create(
        "version2", custom_params={"dynamic_drawdown_rules": custom_rules}
    )

    # 示例4: 策略4使用20日线买入（演示参数覆盖能力）
    strategy_v4_custom = StrategyFactory.create(
        "version4", custom_params={"ma_buy_period": 20}
    )

    print("策略工厂测试通过 ✓")
    print(f"策略1参数: {strategy_v1.params}")
    print(f"策略2自定义规则: {strategy_v2_custom.params['dynamic_drawdown_rules']}")
