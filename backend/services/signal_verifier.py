def verify_signals(raw_signals: dict) -> dict:
    """
    Validates signals before further processing.
    Filters out signals that are too short, irrelevant, or empty.
    Allows passing of complex signals containing 'content' and 'source'.
    """
    print("Executing signal_verifier...")
    verified_signals = {}
    
    for key, signal_data in raw_signals.items():
        if isinstance(signal_data, dict):
            content = signal_data.get("content", "")
            source = signal_data.get("source", "")
        else:
            content = str(signal_data)
            source = "Unknown"
            
        # Verification Rules
        # 1. Signal length > threshold (e.g., > 10 characters)
        if len(content.strip()) > 10:
            verified_signals[key] = {
                "content": content,
                "source": source,
                "verified": True
            }
        else:
            print(f"Signal '{key}' failed verification (too short).")
            
    return verified_signals
