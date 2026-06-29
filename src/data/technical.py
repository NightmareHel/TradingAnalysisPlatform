import math
import pandas as pd
import ta


def _safe(val) -> float | None:
    try:
        f = float(val)
        return None if math.isnan(f) else round(f, 4)
    except (TypeError, ValueError):
        return None


def calculate_all(historical_data: dict) -> dict | None:
    if not historical_data or not historical_data.get("data"):
        return None

    try:
        rows = historical_data["data"]
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)

        # Need at least 30 data points for meaningful indicators
        if len(df) < 30:
            return None

        close = df["close"]
        high = df["high"]
        low = df["low"]
        volume = df["volume"].astype(float)

        # --- Trend ---
        sma20 = _safe(ta.trend.SMAIndicator(close=close, window=20).sma_indicator().iloc[-1])
        sma50 = _safe(ta.trend.SMAIndicator(close=close, window=50).sma_indicator().iloc[-1]) if len(df) >= 50 else None
        sma200 = _safe(ta.trend.SMAIndicator(close=close, window=200).sma_indicator().iloc[-1]) if len(df) >= 200 else None
        ema12 = _safe(ta.trend.EMAIndicator(close=close, window=12).ema_indicator().iloc[-1])
        ema26 = _safe(ta.trend.EMAIndicator(close=close, window=26).ema_indicator().iloc[-1]) if len(df) >= 26 else None

        current_price = _safe(close.iloc[-1])
        price_vs_sma200 = None
        if current_price and sma200:
            price_vs_sma200 = "above" if current_price > sma200 else "below"

        trend_direction = "neutral"
        if sma20 and sma50:
            if sma20 > sma50:
                trend_direction = "uptrend"
            elif sma20 < sma50:
                trend_direction = "downtrend"

        # --- Momentum ---
        rsi_series = ta.momentum.RSIIndicator(close=close, window=14).rsi()
        rsi = _safe(rsi_series.iloc[-1])
        rsi_signal = "neutral"
        if rsi is not None:
            if rsi > 70:
                rsi_signal = "overbought"
            elif rsi < 30:
                rsi_signal = "oversold"

        macd_obj = ta.trend.MACD(close=close)
        macd_line = _safe(macd_obj.macd().iloc[-1])
        macd_signal_val = _safe(macd_obj.macd_signal().iloc[-1])
        macd_hist = _safe(macd_obj.macd_diff().iloc[-1])
        macd_trend = "neutral"
        if macd_line is not None and macd_signal_val is not None:
            macd_trend = "bullish" if macd_line > macd_signal_val else "bearish"

        stoch = ta.momentum.StochasticOscillator(high=high, low=low, close=close)
        stoch_k = _safe(stoch.stoch().iloc[-1])
        stoch_d = _safe(stoch.stoch_signal().iloc[-1])

        # --- Volatility ---
        bb = ta.volatility.BollingerBands(close=close)
        bb_upper = _safe(bb.bollinger_hband().iloc[-1])
        bb_mid = _safe(bb.bollinger_mavg().iloc[-1])
        bb_lower = _safe(bb.bollinger_lband().iloc[-1])
        atr = _safe(ta.volatility.AverageTrueRange(high=high, low=low, close=close, window=14).average_true_range().iloc[-1])

        bb_position = "middle"
        if current_price and bb_upper and bb_lower:
            if current_price > bb_upper:
                bb_position = "above_upper"
            elif current_price > bb_mid:
                bb_position = "upper_half"
            elif current_price > bb_lower:
                bb_position = "lower_half"
            else:
                bb_position = "below_lower"

        # --- Volume ---
        obv_series = ta.volume.OnBalanceVolumeIndicator(close=close, volume=volume).on_balance_volume()
        obv = _safe(obv_series.iloc[-1])
        obv_prev = _safe(obv_series.iloc[-5]) if len(obv_series) >= 5 else None
        obv_trend = "rising" if (obv and obv_prev and obv > obv_prev) else "falling" if (obv and obv_prev) else "neutral"

        # --- Signal interpretations ---
        signals = []
        if rsi is not None:
            if rsi > 70:
                signals.append(f"RSI at {rsi:.1f} — overbought, potential pullback")
            elif rsi < 30:
                signals.append(f"RSI at {rsi:.1f} — oversold, potential bounce")
            else:
                signals.append(f"RSI at {rsi:.1f} — neutral territory")

        if price_vs_sma200:
            signals.append(f"Price {'above' if price_vs_sma200 == 'above' else 'below'} SMA(200) — {'long-term uptrend' if price_vs_sma200 == 'above' else 'long-term downtrend'}")

        if macd_trend != "neutral":
            signals.append(f"MACD {macd_trend} — {'above' if macd_trend == 'bullish' else 'below'} signal line")

        if sma20 and sma50:
            if sma20 > sma50:
                signals.append("SMA(20) above SMA(50) — short-term bullish momentum")
            else:
                signals.append("SMA(20) below SMA(50) — short-term bearish momentum")

        if bb_position in ("above_upper",):
            signals.append("Price above Bollinger upper band — extended, possible mean reversion")
        elif bb_position in ("below_lower",):
            signals.append("Price below Bollinger lower band — oversold on volatility basis")

        if obv_trend == "rising":
            signals.append("OBV rising — volume confirms upward price pressure")
        elif obv_trend == "falling":
            signals.append("OBV falling — volume confirms downward price pressure")

        return {
            "trend": {
                "sma_20": sma20,
                "sma_50": sma50,
                "sma_200": sma200,
                "ema_12": ema12,
                "ema_26": ema26,
                "price_vs_sma200": price_vs_sma200,
                "trend_direction": trend_direction,
            },
            "momentum": {
                "rsi": rsi,
                "rsi_signal": rsi_signal,
                "macd_line": macd_line,
                "macd_signal": macd_signal_val,
                "macd_histogram": macd_hist,
                "macd_trend": macd_trend,
                "stoch_k": stoch_k,
                "stoch_d": stoch_d,
            },
            "volatility": {
                "bb_upper": bb_upper,
                "bb_middle": bb_mid,
                "bb_lower": bb_lower,
                "atr": atr,
                "bb_position": bb_position,
            },
            "volume": {
                "obv": obv,
                "obv_trend": obv_trend,
            },
            "signals": signals,
        }

    except Exception:
        return None
