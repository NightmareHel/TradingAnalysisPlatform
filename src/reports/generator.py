import io
import os
import tempfile
from datetime import datetime
from fpdf import FPDF
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd


DISCLAIMER = "Not financial advice — for informational and educational purposes only."


class StockReport(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 10)
        self.cell(0, 6, "Stock Predictor Report", align="L")
        self.ln(8)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 7)
        self.cell(0, 5, DISCLAIMER, align="C")
        self.ln(3)
        self.cell(0, 5, f"Page {self.page_no()}/{{nb}}", align="C")

    def section_title(self, title):
        self.set_font("Helvetica", "B", 13)
        self.set_fill_color(230, 235, 245)
        self.cell(0, 10, title, fill=True, new_x="LMARGIN", new_y="NEXT")
        self.ln(3)

    def body_text(self, text):
        self.set_font("Helvetica", "", 9)
        self.multi_cell(0, 5, text)
        self.ln(2)

    def key_value(self, key, value):
        self.set_font("Helvetica", "B", 9)
        self.cell(60, 6, key)
        self.set_font("Helvetica", "", 9)
        self.cell(0, 6, str(value), new_x="LMARGIN", new_y="NEXT")


def generate_report(aggregated: dict, prediction: dict) -> bytes | None:
    if not aggregated or not prediction or prediction.get("error"):
        return None

    try:
        pdf = StockReport()
        pdf.alias_nb_pages()

        ticker = aggregated.get("ticker", "UNKNOWN")
        company_name = ""
        if aggregated.get("company_info"):
            company_name = aggregated["company_info"].get("name", ticker)
        currency = prediction.get("currency", "USD")
        symbol = "₹" if currency == "INR" else "$"
        current_price = prediction.get("current_price", 0)

        # --- Cover Page ---
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 28)
        pdf.ln(40)
        pdf.cell(0, 15, "Stock Analysis Report", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 18)
        pdf.cell(0, 12, f"{company_name} ({ticker})", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(5)
        pdf.set_font("Helvetica", "", 14)
        pdf.cell(0, 10, f"Current Price: {symbol}{current_price:,.2f}", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 10, f"Report Date: {datetime.now().strftime('%B %d, %Y')}", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(10)
        market_status = aggregated.get("market_status", {}).get("status_text", "")
        if market_status:
            pdf.set_font("Helvetica", "I", 10)
            pdf.cell(0, 8, market_status, align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(20)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(180, 0, 0)
        pdf.multi_cell(0, 5, DISCLAIMER, align="C")
        pdf.set_text_color(0, 0, 0)

        # --- Executive Summary ---
        pdf.add_page()
        pdf.section_title("Executive Summary")
        pdf.body_text(prediction.get("executive_summary", "No summary available."))

        # Predictions Table
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_fill_color(200, 210, 230)
        headers = ["Timeframe", "Range", "Confidence", "Direction"]
        widths = [35, 50, 35, 50]
        for i, h in enumerate(headers):
            pdf.cell(widths[i], 8, h, border=1, fill=True, align="C")
        pdf.ln()

        pdf.set_font("Helvetica", "", 9)
        labels = {"1d": "1 Day", "1w": "1 Week", "1m": "1 Month", "1y": "1 Year"}
        for tf_key, tf_label in labels.items():
            tf = prediction.get("predictions", {}).get(tf_key, {})
            low = tf.get("price_change_low_pct", 0)
            high = tf.get("price_change_high_pct", 0)
            conf = tf.get("confidence_pct", 0)
            direction = tf.get("direction", "neutral").replace("_", " ").title()
            pdf.cell(widths[0], 7, tf_label, border=1, align="C")
            pdf.cell(widths[1], 7, f"{low:+.1f}% to {high:+.1f}%", border=1, align="C")
            pdf.cell(widths[2], 7, f"{conf}%", border=1, align="C")
            pdf.cell(widths[3], 7, direction, border=1, align="C")
            pdf.ln()

        coverage = aggregated.get("data_coverage", {}).get("overall_coverage_pct", 0)
        pdf.ln(3)
        pdf.body_text(f"Data Coverage: {coverage}%")
        if prediction.get("data_coverage_note"):
            pdf.body_text(prediction["data_coverage_note"])

        # --- Prediction Details ---
        pdf.add_page()
        pdf.section_title("Prediction Details")
        for tf_key, tf_label in labels.items():
            tf = prediction.get("predictions", {}).get(tf_key, {})
            pdf.set_font("Helvetica", "B", 11)
            low = tf.get("price_change_low_pct", 0)
            high = tf.get("price_change_high_pct", 0)
            pdf.cell(0, 8, f"{tf_label}: {low:+.1f}% to {high:+.1f}% (Confidence: {tf.get('confidence_pct', 0)}%)",
                     new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 9)
            if tf.get("bullish_factors"):
                pdf.cell(0, 6, "Bullish Factors:", new_x="LMARGIN", new_y="NEXT")
                for f_item in tf["bullish_factors"]:
                    pdf.cell(5)
                    pdf.multi_cell(0, 5, f"  + {f_item}")
            if tf.get("bearish_factors"):
                pdf.cell(0, 6, "Bearish Factors:", new_x="LMARGIN", new_y="NEXT")
                for f_item in tf["bearish_factors"]:
                    pdf.cell(5)
                    pdf.multi_cell(0, 5, f"  - {f_item}")
            if tf.get("key_catalysts"):
                pdf.cell(0, 6, "Key Catalysts:", new_x="LMARGIN", new_y="NEXT")
                for c in tf["key_catalysts"]:
                    pdf.cell(5)
                    pdf.multi_cell(0, 5, f"  * {c}")
            if tf.get("source_citations"):
                pdf.cell(0, 6, "Sources:", new_x="LMARGIN", new_y="NEXT")
                for s in tf["source_citations"]:
                    pdf.cell(5)
                    pdf.multi_cell(0, 5, f"  [{s}]")
            pdf.ln(4)

        # --- Technical Analysis ---
        if aggregated.get("historical_data") and aggregated.get("technical_indicators"):
            pdf.add_page()
            pdf.section_title("Technical Analysis")

            chart_path = _generate_price_chart(aggregated, ticker, symbol)
            if chart_path:
                pdf.image(chart_path, w=180)
                os.unlink(chart_path)
                pdf.ln(5)

            tech = aggregated["technical_indicators"]
            momentum = tech.get("momentum", {})
            volatility = tech.get("volatility", {})
            trend = tech.get("trend", {})

            indicators = [
                ("RSI (14)", momentum.get("rsi_14"), momentum.get("rsi_interpretation", "")),
                ("MACD", momentum.get("macd_line"), momentum.get("macd_interpretation", "")),
                ("SMA 20", trend.get("sma_20"), trend.get("price_vs_sma20", "")),
                ("SMA 50", trend.get("sma_50"), trend.get("price_vs_sma50", "")),
                ("SMA 200", trend.get("sma_200"), trend.get("price_vs_sma200", "")),
                ("Bollinger Position", "", volatility.get("bollinger_position", "")),
                ("ATR (14)", volatility.get("atr_14"), ""),
            ]

            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(50, 7, "Indicator", border=1, fill=True)
            pdf.cell(35, 7, "Value", border=1, fill=True)
            pdf.cell(0, 7, "Interpretation", border=1, fill=True, new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 8)
            for name, val, interp in indicators:
                pdf.cell(50, 6, name, border=1)
                pdf.cell(35, 6, f"{val:.4f}" if isinstance(val, (int, float)) and val else str(val or "—"), border=1)
                pdf.cell(0, 6, str(interp)[:60], border=1, new_x="LMARGIN", new_y="NEXT")

            signals = tech.get("signals", [])
            if signals:
                pdf.ln(3)
                pdf.set_font("Helvetica", "B", 9)
                pdf.cell(0, 6, "Active Signals:", new_x="LMARGIN", new_y="NEXT")
                pdf.set_font("Helvetica", "", 9)
                for sig in signals:
                    pdf.cell(5)
                    pdf.cell(0, 5, f"• {sig}", new_x="LMARGIN", new_y="NEXT")

        # --- Fundamental Analysis ---
        if aggregated.get("fundamentals"):
            pdf.add_page()
            pdf.section_title("Fundamental Analysis")
            fund = aggregated["fundamentals"]
            coverage = fund.get("coverage_level", "unknown")
            if coverage == "basic":
                pdf.body_text("Note: Basic coverage only (limited data available for this stock)")

            metrics = fund.get("key_metrics", {})
            if metrics:
                for key, val in metrics.items():
                    if val is not None:
                        display_key = key.replace("_", " ").title()
                        if isinstance(val, float):
                            if "margin" in key or "yield" in key or "roe" in key or "roa" in key:
                                pdf.key_value(display_key, f"{val * 100:.1f}%" if abs(val) < 1 else f"{val:.2f}")
                            else:
                                pdf.key_value(display_key, f"{val:,.2f}")
                        else:
                            pdf.key_value(display_key, str(val))

        # --- News & Sentiment ---
        if aggregated.get("news_sentiment"):
            pdf.add_page()
            pdf.section_title("News & Sentiment")
            news_data = aggregated["news_sentiment"]
            avg = news_data.get("average_sentiment", 0)
            sentiment_label = "Positive" if avg > 0.1 else "Negative" if avg < -0.1 else "Neutral"
            pdf.body_text(f"Average Sentiment: {avg:.2f} ({sentiment_label}) from {news_data.get('article_count', 0)} articles")

            for article in news_data.get("articles", [])[:8]:
                pdf.set_font("Helvetica", "B", 8)
                pdf.multi_cell(0, 4, article.get("headline", "")[:100])
                pdf.set_font("Helvetica", "", 7)
                sent = article.get("sentiment")
                sent_str = f"Sentiment: {sent:.2f}" if sent is not None else "Sentiment: N/A"
                pdf.cell(0, 4, f"{article.get('source', '')} | {sent_str}", new_x="LMARGIN", new_y="NEXT")
                pdf.ln(2)

        # --- Insider Trading ---
        if aggregated.get("insider_activity"):
            insider = aggregated["insider_activity"]
            if insider.get("available", True):
                pdf.section_title("Insider & Congressional Trading")
                trades = insider.get("trades", [])
                if trades:
                    pdf.set_font("Helvetica", "", 8)
                    for t in trades[:10]:
                        line = f"{t.get('date', '')} | {t.get('insider_name', '')} | {t.get('transaction_type', '')} | {t.get('shares', '')} shares"
                        pdf.cell(0, 5, line[:100], new_x="LMARGIN", new_y="NEXT")
                    pdf.body_text(f"Net sentiment: {insider.get('net_sentiment', 'neutral')}")
                else:
                    pdf.body_text("No recent insider trades found")
            else:
                pdf.section_title("Insider & Congressional Trading")
                pdf.body_text(f"N/A — {insider.get('reason', 'Not available for this stock')}")

        # --- Legal ---
        if aggregated.get("legal_regulatory"):
            legal = aggregated["legal_regulatory"]
            if legal.get("available", True):
                pdf.section_title("Legal & Regulatory")
                if legal.get("legal_proceedings"):
                    pdf.set_font("Helvetica", "B", 9)
                    pdf.cell(0, 6, "Legal Proceedings (Item 3):", new_x="LMARGIN", new_y="NEXT")
                    pdf.set_font("Helvetica", "", 8)
                    pdf.multi_cell(0, 4, legal["legal_proceedings"][:1500])
                warnings = legal.get("parser_warnings", [])
                if warnings:
                    pdf.ln(2)
                    pdf.set_font("Helvetica", "I", 7)
                    for w in warnings:
                        pdf.multi_cell(0, 4, f"Parser note: {w}")
            else:
                pdf.section_title("Legal & Regulatory")
                pdf.body_text(f"N/A — {legal.get('reason', 'Not available for this stock')}")

        # --- Macro ---
        if aggregated.get("macro_environment"):
            pdf.add_page()
            pdf.section_title("Macroeconomic Environment")
            macro_data = aggregated["macro_environment"]
            indicators = macro_data.get("indicators", {})

            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(55, 7, "Indicator", border=1, fill=True)
            pdf.cell(30, 7, "Value", border=1, fill=True)
            pdf.cell(25, 7, "Change", border=1, fill=True)
            pdf.cell(0, 7, "Trend", border=1, fill=True, new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 8)
            for sid, data in indicators.items():
                pdf.cell(55, 6, data.get("name", sid), border=1)
                pdf.cell(30, 6, f"{data.get('current_value', 0):.2f}", border=1)
                pdf.cell(25, 6, f"{data.get('change_pct', 0):+.1f}%", border=1)
                pdf.cell(0, 6, data.get("trend", ""), border=1, new_x="LMARGIN", new_y="NEXT")

            yc = macro_data.get("yield_curve")
            if yc:
                pdf.ln(3)
                pdf.body_text(f"Yield Curve Spread: {yc.get('spread', 0):.3f}% — {yc.get('interpretation', '')}")

        # --- Risk Assessment ---
        pdf.add_page()
        pdf.section_title("Risk Assessment")
        pdf.body_text(prediction.get("risk_assessment", "No risk assessment available."))

        # --- Sources ---
        pdf.section_title("Sources & Methodology")
        pdf.set_font("Helvetica", "", 8)
        sources = [
            "yfinance — Price data, company info (Yahoo Finance)",
            "Financial Modeling Prep — Company fundamentals, ratios, earnings",
            "Finnhub — News, sentiment analysis, congressional trading",
            "FRED — Macroeconomic indicators (Federal Reserve Bank of St. Louis)",
            "SEC EDGAR / edgartools — SEC filings, legal proceedings, risk factors",
            "SecuritiesDB — Insider trading (SEC Form 4)",
            "ta (Technical Analysis) — RSI, MACD, Bollinger Bands, SMA, OBV",
        ]
        for s in sources:
            pdf.cell(0, 5, f"• {s}", new_x="LMARGIN", new_y="NEXT")

        pdf.ln(5)
        pdf.set_font("Helvetica", "I", 8)
        pdf.multi_cell(0, 4,
            f"Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            "Analysis powered by Claude AI (Anthropic)\n\n"
            f"{DISCLAIMER}")

        output = io.BytesIO()
        pdf.output(output)
        return output.getvalue()
    except Exception:
        return None


def _generate_price_chart(aggregated: dict, ticker: str, symbol: str) -> str | None:
    try:
        hist = aggregated["historical_data"]["data"]
        df = pd.DataFrame(hist)
        df["date"] = pd.to_datetime(df["date"])

        fig, ax = plt.subplots(figsize=(10, 4), dpi=150)
        ax.plot(df["date"], df["close"], color="#2196F3", linewidth=1.2, label="Close")

        if len(df) >= 50:
            ax.plot(df["date"], df["close"].rolling(50).mean(), color="orange", linewidth=0.8, alpha=0.7, label="SMA 50")
        if len(df) >= 200:
            ax.plot(df["date"], df["close"].rolling(200).mean(), color="red", linewidth=0.8, alpha=0.7, label="SMA 200")

        ax.set_title(f"{ticker} — 1 Year Price Chart", fontsize=11)
        ax.set_ylabel(f"Price ({symbol})", fontsize=9)
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
        fig.autofmt_xdate()
        fig.tight_layout()

        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        fig.savefig(tmp.name, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return tmp.name
    except Exception:
        return None
