"""
Test script for Kerykeion MCP Server tools.
This tests each tool and saves outputs to the test_outputs directory.
"""

import json
import os
from pathlib import Path

# Add src to path
import sys
sys.path.insert(0, str(Path(__file__).parent / "src"))

from kerykeion_mcp.server import (
    generate_natal_chart,
    generate_synastry_chart,
    generate_transit_chart,
    generate_composite_chart,
    generate_planetary_return,
    generate_event_chart,
    get_current_positions,
)

OUTPUT_DIR = Path(__file__).parent / "test_outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

# Test data
BIRTH_DATA_1 = {
    "name": "Test Person 1",
    "year": 1990, "month": 6, "day": 15,
    "hour": 14, "minute": 30,
    "lat": 41.9028, "lng": 12.4964,
    "tz_str": "Europe/Rome",
}

BIRTH_DATA_2 = {
    "name": "Test Person 2", 
    "year": 1992, "month": 12, "day": 25,
    "hour": 16, "minute": 45,
    "lat": 51.5074, "lng": -0.1278,
    "tz_str": "Europe/London",
}


def save_result(name: str, result: dict):
    """Save result to JSON file, extracting image data separately."""
    # Separate images from text data
    text_result = {}
    for key, value in result.items():
        if key in ("svg", "png"):
            # Save image data to separate file
            ext = "svg" if key == "svg" else "png"
            img_path = OUTPUT_DIR / f"{name}.{ext}"
            
            # Extract from data URI
            if value.startswith("data:"):
                import base64
                # Find the base64 part
                _, encoded = value.split(",", 1)
                img_data = base64.b64decode(encoded)
                img_path.write_bytes(img_data)
                text_result[key] = f"[Saved to {name}.{ext}]"
            else:
                text_result[key] = f"[Image data: {len(value)} chars]"
        else:
            text_result[key] = value
    
    # Save JSON with text content
    json_path = OUTPUT_DIR / f"{name}.json"
    with open(json_path, "w") as f:
        json.dump(text_result, f, indent=2, default=str)
    
    return text_result


def test_all():
    """Test all MCP tools."""
    results = {}
    
    # 1. Test generate_natal_chart
    print("Testing generate_natal_chart...")
    try:
        result = generate_natal_chart(
            output_format="all",
            **BIRTH_DATA_1
        )
        text_result = save_result("natal_chart", result)
        results["natal_chart"] = {
            "status": "OK",
            "text_length": len(result.get("text", "")),
            "has_svg": "svg" in result,
            "has_png": "png" in result,
        }
        print(f"  ✓ Text: {len(result.get('text', ''))} chars")
    except Exception as e:
        results["natal_chart"] = {"status": "ERROR", "error": str(e)}
        print(f"  ✗ Error: {e}")

    # 2. Test generate_event_chart
    print("Testing generate_event_chart...")
    try:
        result = generate_event_chart(
            event_name="Test Event",
            year=2024, month=1, day=1,
            hour=12, minute=0,
            lat=40.7128, lng=-74.0060,
            tz_str="America/New_York",
            output_format="all",
        )
        save_result("event_chart", result)
        results["event_chart"] = {
            "status": "OK",
            "text_length": len(result.get("text", "")),
            "has_svg": "svg" in result,
            "has_png": "png" in result,
        }
        print(f"  ✓ Text: {len(result.get('text', ''))} chars")
    except Exception as e:
        results["event_chart"] = {"status": "ERROR", "error": str(e)}
        print(f"  ✗ Error: {e}")

    # 3. Test generate_synastry_chart
    print("Testing generate_synastry_chart...")
    try:
        result = generate_synastry_chart(
            name1=BIRTH_DATA_1["name"],
            year1=BIRTH_DATA_1["year"], month1=BIRTH_DATA_1["month"], day1=BIRTH_DATA_1["day"],
            hour1=BIRTH_DATA_1["hour"], minute1=BIRTH_DATA_1["minute"],
            lat1=BIRTH_DATA_1["lat"], lng1=BIRTH_DATA_1["lng"], tz_str1=BIRTH_DATA_1["tz_str"],
            name2=BIRTH_DATA_2["name"],
            year2=BIRTH_DATA_2["year"], month2=BIRTH_DATA_2["month"], day2=BIRTH_DATA_2["day"],
            hour2=BIRTH_DATA_2["hour"], minute2=BIRTH_DATA_2["minute"],
            lat2=BIRTH_DATA_2["lat"], lng2=BIRTH_DATA_2["lng"], tz_str2=BIRTH_DATA_2["tz_str"],
            output_format="all",
        )
        save_result("synastry_chart", result)
        results["synastry_chart"] = {
            "status": "OK",
            "text_length": len(result.get("text", "")),
            "has_svg": "svg" in result,
            "has_png": "png" in result,
            "relationship_score": result.get("relationship_score"),
        }
        print(f"  ✓ Text: {len(result.get('text', ''))} chars, Score: {result.get('relationship_score')}")
    except Exception as e:
        results["synastry_chart"] = {"status": "ERROR", "error": str(e)}
        print(f"  ✗ Error: {e}")

    # 4. Test generate_transit_chart
    print("Testing generate_transit_chart...")
    try:
        result = generate_transit_chart(
            natal_name=BIRTH_DATA_1["name"],
            natal_year=BIRTH_DATA_1["year"], natal_month=BIRTH_DATA_1["month"], natal_day=BIRTH_DATA_1["day"],
            natal_hour=BIRTH_DATA_1["hour"], natal_minute=BIRTH_DATA_1["minute"],
            natal_lat=BIRTH_DATA_1["lat"], natal_lng=BIRTH_DATA_1["lng"], natal_tz_str=BIRTH_DATA_1["tz_str"],
            transit_lat=BIRTH_DATA_1["lat"], transit_lng=BIRTH_DATA_1["lng"], transit_tz_str=BIRTH_DATA_1["tz_str"],
            output_format="all",
        )
        save_result("transit_chart", result)
        results["transit_chart"] = {
            "status": "OK",
            "text_length": len(result.get("text", "")),
            "has_svg": "svg" in result,
            "has_png": "png" in result,
        }
        print(f"  ✓ Text: {len(result.get('text', ''))} chars")
    except Exception as e:
        results["transit_chart"] = {"status": "ERROR", "error": str(e)}
        print(f"  ✗ Error: {e}")

    # 5. Test generate_composite_chart
    print("Testing generate_composite_chart...")
    try:
        result = generate_composite_chart(
            name1=BIRTH_DATA_1["name"],
            year1=BIRTH_DATA_1["year"], month1=BIRTH_DATA_1["month"], day1=BIRTH_DATA_1["day"],
            hour1=BIRTH_DATA_1["hour"], minute1=BIRTH_DATA_1["minute"],
            lat1=BIRTH_DATA_1["lat"], lng1=BIRTH_DATA_1["lng"], tz_str1=BIRTH_DATA_1["tz_str"],
            name2=BIRTH_DATA_2["name"],
            year2=BIRTH_DATA_2["year"], month2=BIRTH_DATA_2["month"], day2=BIRTH_DATA_2["day"],
            hour2=BIRTH_DATA_2["hour"], minute2=BIRTH_DATA_2["minute"],
            lat2=BIRTH_DATA_2["lat"], lng2=BIRTH_DATA_2["lng"], tz_str2=BIRTH_DATA_2["tz_str"],
            output_format="all",
        )
        save_result("composite_chart", result)
        results["composite_chart"] = {
            "status": "OK",
            "text_length": len(result.get("text", "")),
            "has_svg": "svg" in result,
            "has_png": "png" in result,
        }
        print(f"  ✓ Text: {len(result.get('text', ''))} chars")
    except Exception as e:
        results["composite_chart"] = {"status": "ERROR", "error": str(e)}
        print(f"  ✗ Error: {e}")

    # 6. Test generate_planetary_return
    print("Testing generate_planetary_return (Solar Return)...")
    try:
        result = generate_planetary_return(
            return_type="Solar",
            return_year=2024,
            output_format="all",
            **BIRTH_DATA_1
        )
        save_result("solar_return", result)
        results["solar_return"] = {
            "status": "OK",
            "text_length": len(result.get("text", "")),
            "has_svg": "svg" in result,
            "has_png": "png" in result,
            "return_date": result.get("return_date"),
        }
        print(f"  ✓ Text: {len(result.get('text', ''))} chars, Date: {result.get('return_date')}")
    except Exception as e:
        results["solar_return"] = {"status": "ERROR", "error": str(e)}
        print(f"  ✗ Error: {e}")

    # 7. Test get_current_positions
    print("Testing get_current_positions...")
    try:
        result = get_current_positions(
            lat=BIRTH_DATA_1["lat"],
            lng=BIRTH_DATA_1["lng"],
            tz_str=BIRTH_DATA_1["tz_str"],
        )
        save_result("current_positions", result)
        results["current_positions"] = {
            "status": "OK",
            "text_length": len(result.get("text", "")),
            "lunar_phase": result.get("lunar_phase"),
        }
        print(f"  ✓ Text: {len(result.get('text', ''))} chars")
    except Exception as e:
        results["current_positions"] = {"status": "ERROR", "error": str(e)}
        print(f"  ✗ Error: {e}")

    # Save summary
    summary_path = OUTPUT_DIR / "test_summary.json"
    with open(summary_path, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n=== Test Summary ===")
    print(f"Results saved to: {OUTPUT_DIR}")
    for name, info in results.items():
        status = "✓" if info.get("status") == "OK" else "✗"
        print(f"  {status} {name}: {info.get('status')}")
    
    return results


if __name__ == "__main__":
    test_all()
