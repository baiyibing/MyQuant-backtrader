//! 换手阻力全市场计算 — CLI 入口（轻量包装，核心逻辑在 `engine` 模块）。

use std::io::Write;
use std::path::PathBuf;

use anyhow::Result;
use clap::Parser;

use turnover_resist::cli::Cli;

fn main() -> Result<()> {
    let t_total = std::time::Instant::now();

    // ---- 1. 解析命令行参数 ----
    let cli = Cli::parse();

    anyhow::ensure!(cli.window >= 20, "--window must be >= 20");
    anyhow::ensure!(cli.step > 0.0, "--step must be > 0");

    let date_str = cli.date.format("%Y%m%d").to_string();
    let output_path = cli.output.clone().unwrap_or_else(|| {
        PathBuf::from(format!(
            "backtest_output/canonical_resist_rust_{}.csv",
            date_str
        ))
    });

    // ---- 2. 核心计算（engine 模块） ----
    let results = turnover_resist::engine::run(&cli)?;

    // ---- 3. 输出 CSV（UTF-8 BOM） ----
    if let Some(parent) = output_path.parent() {
        std::fs::create_dir_all(parent)?;
    }

    let file = std::fs::File::create(&output_path)?;
    let mut writer = std::io::BufWriter::new(file);

    // UTF-8 BOM
    writer.write_all(&[0xEF, 0xBB, 0xBF])?;

    let mut csv_writer = csv::Writer::from_writer(writer);
    for row in &results {
        csv_writer.serialize(row)?;
    }
    csv_writer.flush()?;

    // ---- 4. 打印结果摘要 + Top 20 ----
    let t_total_elapsed = t_total.elapsed();
    eprintln!(
        "\n[Timing] total={:.1}s  rows={}",
        t_total_elapsed.as_secs_f64(),
        results.len()
    );
    let top_key = match cli.sort_by {
        turnover_resist::cli::SortBy::Circulating => "|turnover_resistance|",
        turnover_resist::cli::SortBy::Free => "|turnover_resistance_free|",
    };
    eprintln!("\nTop 20 by {}:", top_key);
    for (i, row) in results.iter().take(20).enumerate() {
        eprintln!(
            "  {:2}. {:>9} {:>8} resist={:>10.4} cyqk_T={:>8.4} cyqk_T_1={:>8.4} turnover={:>10.6}",
            i + 1,
            row.stock_code,
            row.stock_name,
            row.turnover_resistance,
            row.cyqk_t,
            row.cyqk_t_1,
            row.turnover,
        );
    }

    Ok(())
}
