def classify_signals(verified_signals: dict) -> dict:
    """
    Classifies signals into specific S1-S6 categories based on keyword mappings.
    If a signal doesn't perfectly match, it maps it to the closest category or retains its general label.
    """
    print("Executing signal_classifier...")
    
    classified_signals = {}
    
    # Simple keyword-based classifier mapping
    category_map = {
        "hiring": "S1 Hiring signals",
        "funding": "S2 Funding signals",
        "leadership": "S3 Leadership changes",
        "product_launch": "S4 Product launches",
        "expansion": "S5 Hiring expansion",
        "market": "S6 Market reputation signals",
        "social": "S6 Market reputation signals",
        "news": "S6 Market reputation signals",
        "tech_stack": "S6 Market reputation signals"
    }

    for key, signal_data in verified_signals.items():
        # Match using the key first
        matched_category = None
        for keyword, mapped_category in category_map.items():
            if keyword in key.lower():
                matched_category = mapped_category
                break
                
        # If no key match, scan the content text
        if not matched_category:
            content_lower = signal_data.get("content", "").lower()
            if "hire" in content_lower or "recruit" in content_lower:
                matched_category = category_map["hiring"]
            elif "fund" in content_lower or "raise" in content_lower:
                matched_category = category_map["funding"]
            elif "launch" in content_lower or "release" in content_lower:
                matched_category = category_map["product_launch"]
            else:
                matched_category = "General Company Intel"

        # Append to classified output
        if matched_category not in classified_signals:
            classified_signals[matched_category] = []
            
        classified_signals[matched_category].append({
            "original_key": key,
            "content": signal_data.get("content"),
            "source": signal_data.get("source")
        })

    return classified_signals
