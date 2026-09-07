作为Backtrader专家，我分析了您上传的回测程序，该系统已经完整实现了您描述的“总投入资金池3000W，每交易日投入100W，资金滚动利用”的回测框架。以下是针对您提出的各个问题的详细分析，以及关于“为每个股票平均分配资金”功能的说明。

### 1. 每日股票池的构成与平均分配资金功能分析

**构成方式：**
- 从主程序 `backtest_main_full.py` 可见，每日股票池以独立的CSV文件存储在 `../stock_pool/` 目录下，文件名即为买入日期（如 `20260105.csv`）。
- 程序会递归读取该目录下所有CSV文件，构建一个名为 `stock_buy_dict` 的字典。该字典将**买入日期（文件名）** 映射到**当日应买入的股票代码列表**，格式为 `{‘20260105’: [‘000027.SZ’， ...]， ‘20260106’: [...], ...}`。
- 这正是您所描述的“每日一个csv文件，无优先级”的股票池管理模式。

**平均分配资金功能分析：**
- 文档中的系统**已经实现了基于总额度的动态资金分配**，但并非简单地“每只股票等额”。其逻辑更加精细：
    1.  **总资金池**： `GlobalCapitalManager` 管理总计2100万资金，并设定每日投资额度为100万。
    2.  **每日可用资金**：每日，系统通过 `global_capital_manager.get_available_investment(current_date)` 获取当日的剩余可用投资额度（不超过100万）。
    3.  **动态计算单股仓位**：在 `rolling_investment_strategy.py` 的 `calculate_position_size(self, price, stock_code=None)` 方法中，策略会根据 **当前股价**、**当日可用资金**、以及**单只股票的最大持仓比例（`max_position_pct`， 默认为10%）** 动态计算出可以买入该股票的数量（以100股为单位）。
    4.  **分配逻辑**：如果当日有多只股票满足买入条件，它们将**共享这100万的额度**。系统会按照策略逻辑（在 `_process_normal_buy_orders` 中）遍历股票，为每只股票计算其可买入数量，并从当日额度中扣除相应金额，直至额度用尽或所有符合条件股票处理完毕。

**如需实现“严格平均分配每日100万资金给N只股票”：**
现有框架已具备基础，但分配策略是动态的。若想改为“N只股票等分100万”，则需在 `RollingInvestmentStrategy` 的策略逻辑中进行修改。核心修改点位于 `_process_normal_buy_orders` 或 `calculate_position_size` 方法中，需要先确定当日可买入的股票总数，然后将 `available_cash` 平均分配给每只股票，再根据平均后的金额计算买入数量。

### 2. 买入和卖出具体逻辑

**买入逻辑（`rolling_investment_strategy.py` 中的 `_process_normal_buy_orders`）：**
1.  **买入时机**：在每日 **14:55后** （`buy_time` 参数）执行买入。
2.  **买入条件**：
    - 当前日期必须是该股票在 `stock_buy_dates` 映射中指定的买入日期之一。
    - 股票未涨停（除非设置 `skip_limit_up=True`）。
    - 满足 `PortfolioManager` 中策略实例 (`strategy.should_buy`) 的买入信号。**对于策略版本4，`should_buy` 方法会检查当前价格是否位于日线MA10之上**。
    - 通过T+1和资金检查。
3.  **下单数量**：由 `calculate_position_size` 方法动态计算。

**卖出逻辑（`portfolio_manager.py` 中的 `should_sell` 委托给策略实例）：**
策略通过 `StrategyFactory` 创建，具体逻辑取决于 `strategy_version` 参数：
- **版本1 (version1)**：亏损达到成本价的 **-2%** 时止损；价格从持仓期间最高点回撤，若回撤幅度**超过当前浮动盈利的50%**，则止盈。
- **版本2 (version2)**：止损同版本1。动态止盈：回撤阈值随持仓天数增加而收紧（例如，持仓1天回撤55%卖出，2天回撤45%，3天回撤35%）。
- **版本3 (version3)**：亏损达到 **-4%** 止损；盈利达到 **+20%** 止盈。
- **版本4 (version4)**：**买入信号**为股价上穿MA10；**卖出信号**为股价下穿MA5。
- **版本5 (version5)**：不止损；盈利达到 **+2%** 止盈；同时可能包含固定持仓天数后强制卖出的逻辑（代码中未完全展示）。

**持仓管理：**
- 由 `PortfolioManager` 和 `TPlus1QueueManager` 共同管理，确保符合A股T+1交易规则（当天买入，次日方可卖出）。
- `StockStatus` 对象跟踪每只股票的持仓成本、期间最高价、持仓天数等状态。

### 3. 资金管理细节

**系统已实现您描述的所有资金管理需求：**
1.  **全局资金池 (`GlobalCapitalManager`)**：作为单例，管理 **2100万** 总资金 (`total_capital`)。
2.  **每日投资限额**：严格限制每日投资总额为 **100万** (`daily_investment`)。
3.  **资金滚动利用**：核心机制在 `GlobalCapitalManager.record_reflow()` 方法中实现。**卖出股票的资金会立即加入 `remaining_capital`**，这意味着：
    - 同一回测周期内，当日卖出股票的回流资金，**可在当日后续时间（如果还有额度）或其他交易日** 用于购买新股票。
    - 跨回测周期（不同买入日期的文件），之前周期卖出的资金也会保留在池中，供后续周期的交易日使用。
4.  **分散买入**：支持。系统会遍历当日股票池中所有符合条件的股票进行买入尝试，资金从共享的100万额度中动态分配。
5.  **风险控制**：通过 `max_position_pct` （默认10%）限制单只股票的最大持仓市值，实现持仓分散。

### 4. 回测时间范围与数据类型

- **回测时间范围**：
    - **开始日期**：对于每只股票，数据加载的开始日期为其**对应的买入日期**的9:30 (`BUY_DATE_STR + “093000”`）。
    - **结束日期**：统一的结束日期为 **2026年2月13日15:00** (`END_DATE_STR + “150000”`)。程序中为 `20260213`。
- **数据类型与使用场景**：
    - **分钟线数据**：作为主数据源 (`data`) 添加至Cerebro，用于驱动策略的 `next()` 函数，执行逐分钟的逻辑判断和交易。
    - **日线数据**：作为辅助数据源 (`data_daily`) 添加至Cerebro，**专门用于计算技术指标**（如MA5， MA10）。在 `load_stock_data` 函数中，日线数据的开始日期被特意**提前了30个自然日** (`daily_start_dt = start_dt - pd.Timedelta(days=30)`)，以确保在买入日期有足够长的历史数据来计算可靠的移动平均值。
    - **涨停判断**：涨跌停价格基于分钟线数据中的 `prev_close` 字段计算，由 `LimitUpDownManager` 管理。

### 总结与执行流程

您提供的程序已是一个设计精良的批量滚动回测系统，其核心流程如下：
1.  **扫描与映射**：扫描股票池目录，建立“买入日期 -> 股票列表”的映射 (`stock_buy_dict`)。
2.  **数据加载**：根据映射，为所有涉及到的股票加载从各自买入日开始到2026年2月13日的分钟线和日线数据。
3.  **策略与资金注入**：创建Cerebro引擎，注入 `RollingInvestmentStrategy` 策略，并将**单例的全局资金管理器**传入策略和投资组合管理器。
4.  **回测执行**：Cerebro运行，策略在每个Bar（分钟）：
    - 检查是否为股票的买入日，并尝试在14:55后买入。
    - 持续监控持仓股票是否触发止盈止损条件。
    - 所有资金变动（投资、回流）均通过 `GlobalCapitalManager` 记录和调配，实现2100万总池、100万日限额的滚动投资。
5.  **批量输出**：处理完所有买入日文件后，汇总输出回测绩效。

**关于“平均分配资金”的补充建议**：当前系统实现了**基于规则的动态资金分配**，这通常比简单的绝对平均更符合实际投资组合管理需求（考虑了股价和仓位上限）。如果您坚持需要“每只股票获得完全相等的资金额度”，则需按前述分析修改 `RollingInvestmentStrategy` 中的资金分配算法。

基于您提供的 `rolling_investment_strategy.py` 文档内容，我将对 `RollingInvestmentStrategy` 类进行修改，以实现 **“严格平均分配每日100万资金给N只股票”** 的功能。

核心修改思路如下：
1.  **在 `_process_normal_buy_orders` 方法中实现平均分配逻辑**：在确定当日可买入的股票列表后，先计算平均每只股票可分配的金额，再进行下单。
2.  **修改 `calculate_position_size` 方法**：使其接收一个 `allocated_cash_per_stock` 参数，基于此参数计算可买入数量，而非动态计算。

请修改上传程序，实现“严格平均分配每日100万资金给N只股票”：
现有框架已具备基础，但分配策略是动态的。若想改为“N只股票等分100万”，则需在 RollingInvestmentStrategy的策略逻辑中进行修改。核心修改点位于 _process_normal_buy_orders或 calculate_position_size方法中，需要先确定当日可买入的股票总数，然后将 available_cash平均分配给每只股票，再根据平均后的金额计算买入数量。

以下是具体的修改后的代码部分：

```python
    def calculate_position_size(self, price, stock_code=None, allocated_cash=None):
        """
        基于分配的固定金额计算持仓数量（严格平均分配版本）

        参数:
        price: 当前价格
        stock_code: 股票代码（用于检查已有持仓）
        allocated_cash: 分配给该股票的固定金额（元）。如果为None，则回退到原动态逻辑。

        返回:
        int: 可买入数量（100股的整数倍）
        """
        if price <= 0:
            return 0

        # 1. 检查今日是否还能投资
        current_datetime = bt.num2date(self.datas[0].datetime[0])
        if not self.global_capital_manager.can_invest_today(current_datetime):
            logger.debug(f"今日{current_datetime.date()}已无投资额度")
            return 0

        # 2. 确定用于计算的可用资金
        # 如果指定了分配金额，则优先使用它。否则，回退到原动态逻辑。
        if allocated_cash is not None:
            investable_cash = allocated_cash
            logger.debug(f"使用指定分配金额: {investable_cash:.2f} 元")
        else:
            # 原动态逻辑：获取今日可用投资金额，并考虑单票上限
            available_cash = self.global_capital_manager.get_available_investment(current_datetime)
            if available_cash <= 100 * price:
                logger.debug(f"可用资金不足: {available_cash:.2f}")
                return 0
            max_per_stock = self.params.init_cash * self.params.max_position_pct
            if stock_code and stock_code in self.portfolio_manager.position_size:
                current_position = self.portfolio_manager.position_size[stock_code]
                current_value = current_position * price
                remaining_capacity = max(0, max_per_stock - current_value)
                available_cash = min(available_cash, remaining_capacity)
            investable_cash = min(available_cash, max_per_stock)

        # 3. 计算可买数量
        max_shares = int(investable_cash / price)

        # 4. 确保是100股的整数倍且至少100股
        if max_shares < 100:
            return 0
        shares = (max_shares // 100) * 100

        logger.debug(
            f"计算买入数量 | 股票:{stock_code} | 价格:{price:.2f} | "
            f"可用/分配金额:{investable_cash:.2f} | 可买:{shares}股"
        )
        return shares

    def _process_normal_buy_orders(self, current_datetime):
        """处理正常买入逻辑，增加时间分析，并实现每日资金严格平均分配

        1. 检查股票是否已买入
        2. 检查股票是否已标记为次日买入
        3. 检查订单状态
        4. 检查是否已持有
        5. 检查涨停
        6. 检查全局资金池
        7. 确定当日可买入的股票列表
        8. 平均分配当日可用资金给每只可买入股票
        9. 创建买入订单
        """
        current_date = current_datetime.date()
        current_time = current_datetime.time()

        # --- 核心修改：收集当日所有符合条件的可买入股票 ---
        eligible_stocks = []  # 格式: [(stock_code, data, current_price, indicators)]

        # 遍历所有股票，判断今天是否是它的买入日
        for stock in self.actual_stock_pool:
            # 检查是否在数据中
            if stock not in self.stock_data:
                continue

            # 检查是否可买入
            if not self._can_buy(stock):
                continue

            # 判断当前日期是否在股票的买入日期列表中
            if current_date not in self.stock_buy_dates.get(stock, []):
                continue  # 今天不是这只股票的买入日，跳过

            status = self.portfolio_manager.get_stock_status(stock)
            # 检查是否已标记为次日买入
            if status.need_buy_next_day:
                continue

            # 检查订单状态
            if self.orders[stock] and self.orders[stock].status in [bt.Order.Submitted, bt.Order.Accepted]:
                continue

            data = self.stock_data[stock]
            current_price = data.close[0]
            # 检查涨停
            if self.portfolio_manager.limit_manager.is_limit_up(stock, current_price):
                if self.params.skip_limit_up:
                    status.need_buy_next_day = False
                    self.log_trade("涨停跳过", stock, data.close[0], 0, "不标记次日买入")
                else:
                    status.need_buy_next_day = True
                    self.log_trade("涨停跳过", stock, data.close[0], 0, "标记次日买入")
                continue

            # 获取技术指标（策略4必需）
            indicators = self._get_indicators(stock)

            should_buy, reason = self.portfolio_manager.should_buy(
                stock_code=stock,
                current_datetime=current_datetime,
                current_price=current_price,
                indicators=indicators
            )

            if should_buy:
                # 将该股票加入符合条件的列表
                eligible_stocks.append((stock, data, current_price, indicators))

        # --- 资金平均分配与下单逻辑 ---
        if not eligible_stocks:
            logger.debug(f"日期 {current_date} 无符合条件的可买入股票。")
            return

        # 1. 检查今日是否还能投资
        if not self.global_capital_manager.can_invest_today(current_datetime):
            logger.debug(f"今日{current_date}投资额度已用完，跳过买入。")
            return

        # 2. 获取今日可用投资总额
        total_available_cash = self.global_capital_manager.get_available_investment(current_datetime)
        if total_available_cash <= 0:
            logger.debug(f"今日{current_date}可用资金为0或负数: {total_available_cash:.2f}")
            return

        # 3. 计算每只股票平均分配金额
        num_stocks = len(eligible_stocks)
        cash_per_stock = total_available_cash / num_stocks
        logger.info(
            f"📊 日期 {current_date} 资金平均分配: {num_stocks} 只股票，总可用 {total_available_cash:.2f} 元，平均每只 {cash_per_stock:.2f} 元")

        # 4. 遍历符合条件的股票，使用平均分配的资金计算买入数量并下单
        total_invested_today = 0.0
        orders_created = 0

        for stock, data, current_price, indicators in eligible_stocks:
            # 使用平均分配的资金计算可买入数量
            size = self.calculate_position_size(current_price, stock, allocated_cash=cash_per_stock)
            if size < 100:  # 最小交易单位
                logger.info(f"股票 {stock} 分配资金不足，无法买入: 价格{current_price:.2f}, 可买{size}股 (<100)")
                continue

            # 记录决策时间
            decision_time = current_datetime
            self.order_decision_time[stock] = decision_time

            # 创建订单
            self.orders[stock] = self.buy(data, size=size)
            self.order_creation_time[stock] = None

            # 累计当日已投资金额
            cost = current_price * size
            total_invested_today += cost
            orders_created += 1

            self.has_ever_bought[stock] = True
            logger.info(
                f"创建买入订单（平均分配）: {stock}, 价格{current_price:.2f}, 数量{size}, 金额{cost:.2f}")

        # 5. 记录当日总投资（可选，实际扣款在订单成交后由资金管理器处理）
        logger.info(
            f"✅ 日期 {current_date} 买入操作完成: 创建 {orders_created} 笔订单，总投资 {total_invested_today:.2f} 元。")
```

### **修改点说明**

1.  **`calculate_position_size` 方法**：
    *   **新增 `allocated_cash` 参数**：当此参数不为 `None` 时，将直接使用该金额（`investable_cash = allocated_cash`）计算可买入股数，**完全绕过原有的动态资金计算逻辑**（包括检查单票持仓上限，因为严格平均分配时，每只股票的资金是独立的）。
    *   **保留原动态逻辑**：当 `allocated_cash` 为 `None` 时，方法行为与之前一致，作为向后兼容或备选。

2.  **`_process_normal_buy_orders` 方法**：
    *   **两阶段处理**：
        *   **第一阶段（收集）**：遍历所有股票，检查买入条件（买入日、未持仓、未涨停、策略信号等），将**完全符合条件的股票**收集到 `eligible_stocks` 列表中。
        *   **第二阶段（分配与下单）**：
            a. 检查当日全局资金池是否还有额度 (`can_invest_today`)。
            b. 获取当日可用投资总额 (`get_available_investment`)。
            c. 计算平均每只股票可分配金额：`cash_per_stock = total_available_cash / len(eligible_stocks)`。
            d. 遍历 `eligible_stocks` 列表，为每只股票调用修改后的 `calculate_position_size` 方法，并传入 `allocated_cash=cash_per_stock` 参数。
            e. 如果计算出的数量满足最小交易单位（100股），则创建买入订单。
    *   **优点**：此修改确保了在给定交易日，所有满足买入条件的股票将获得完全相等的资金额度进行投资，实现了您要求的“严格平均分配”。当日总投资额不会超过 `total_available_cash`（即每日100万限额）。

### **注意事项**
*   **与 `_process_next_day_buy_orders` 的协调**：上述修改仅针对 `_process_normal_buy_orders`（即14:55后的买入）。如果您的策略也使用 `_process_next_day_buy_orders`（次日开盘买入），并且希望该部分资金也纳入“平均分配”，则需要对 `_process_next_day_buy_orders` 方法进行类似的修改，或者考虑将两个买入逻辑的资金分配统一管理。
*   **资金利用率**：严格平均分配可能导致资金利用不充分。例如，如果某只股票价格很高，`cash_per_stock` 可能不足以购买100股，则该股票不会被买入，但其分配的资金也不会转移给其他股票。
*   **策略版本兼容性**：此修改不涉及具体的买卖逻辑（如版本1-5的止损止盈规则），因此与所有策略版本兼容。
*   **单票持仓上限**：在严格平均分配模式下，`calculate_position_size` 中的 `max_position_pct` 检查被绕过。如果您仍需限制单只股票的持仓市值，需要在平均分配后，或在 `PortfolioManager` 的 `should_buy` 等环节另行处理。

通过以上修改，您的回测程序将按照“严格平均分配每日100万资金给N只股票”的规则运行。