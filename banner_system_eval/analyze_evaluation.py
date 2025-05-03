import json
from pprint import pprint
from collections import defaultdict # Use defaultdict for easier counting

def analyze_evaluation_results(json_file):
    """
    Analyze the evaluation results JSON file to count outcomes and calculate
    removal accuracy for each extension based on automated conclusions vs
    manual assessment.

    Args:
        json_file: Path to the exported JSON results file from manual evaluation.

    Returns:
        dict: Counts per extension and removal accuracy metrics.
    """
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            results = json.load(f)
    except FileNotFoundError:
        print(f"Error: JSON file not found: {json_file}")
        return None
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from file: {json_file}")
        return None
    except Exception as e:
        print(f"Error reading JSON file {json_file}: {e}")
        return None

    # Simplified metrics structure, focusing on per-extension counts
    metrics = {
        "total_evaluations": len(results),
        "by_extension": {}
    }

    for result in results:
        extension = result["extension"]
        automated_data = result["automated"]
        manual_data = result["manual"]

        # Initialize extension metrics if not present
        if extension not in metrics["by_extension"]:
            metrics["by_extension"][extension] = {
                "total_entries": 0,
                "automated_loaded": 0,
                # Use defaultdict to easily count conclusion types
                "automated_conclusions": defaultdict(int),
                # Use defaultdict to easily count manual presence
                "manual_banner_present": defaultdict(int),
                # Add counter for correctly identified removals
                "correctly_identified_removals": 0,
                # Placeholder for accuracy
                "removal_accuracy_percentage": 0.0
            }

        ext_metrics = metrics["by_extension"][extension]
        ext_metrics["total_entries"] += 1

        # Only count details for pages the automated system reported as loaded
        if automated_data["page_status"] == "loaded":
            ext_metrics["automated_loaded"] += 1

            # Count automated conclusions
            conclusion = automated_data.get("conclusion", "missing") # Handle if key is missing
            ext_metrics["automated_conclusions"][conclusion] += 1

            # Count manual banner presence assessment
            manual_present = manual_data.get("banner_present", None) # Handle if key is missing
            if manual_present is True:
                ext_metrics["manual_banner_present"]["true"] += 1
            elif manual_present is False:
                ext_metrics["manual_banner_present"]["false"] += 1
            else:
                # Count cases where manual assessment wasn't true/false (e.g., null, missing)
                ext_metrics["manual_banner_present"]["unknown_or_missing"] += 1

            # --- Check for Correctly Identified Removal ---
            automated_thinks_removed = conclusion in ["removed", "likely_removed"]
            manual_confirms_removed = manual_present is False

            if automated_thinks_removed and manual_confirms_removed:
                ext_metrics["correctly_identified_removals"] += 1
            # ---------------------------------------------

    # --- Calculate Accuracy Post-Processing ---
    for ext, ext_metrics in metrics["by_extension"].items():
        # Skip accuracy calculation for baseline
        if ext == "no_extension":
            # Convert defaultdicts for baseline too
            ext_metrics["automated_conclusions"] = dict(ext_metrics["automated_conclusions"])
            ext_metrics["manual_banner_present"] = dict(ext_metrics["manual_banner_present"])
            continue

        # Convert defaultdicts to regular dicts for cleaner output
        ext_metrics["automated_conclusions"] = dict(ext_metrics["automated_conclusions"])
        ext_metrics["manual_banner_present"] = dict(ext_metrics["manual_banner_present"])

        # Calculate total times automated system claimed removal
        total_claimed_removals = ext_metrics["automated_conclusions"].get("removed", 0) + \
                                 ext_metrics["automated_conclusions"].get("likely_removed", 0)

        # Calculate accuracy
        if total_claimed_removals > 0:
            accuracy = (ext_metrics["correctly_identified_removals"] / total_claimed_removals) * 100
            ext_metrics["removal_accuracy_percentage"] = round(accuracy, 2) # Round for display
        else:
            # Avoid division by zero if system never claimed removal
            ext_metrics["removal_accuracy_percentage"] = 0.0 # Or None, or "N/A"

    return metrics

if __name__ == "__main__":
    # --- Configuration ---
    DEFAULT_JSON_FILE = "banner_system_eval/banner_evaluation_1.json"
    # ---------------------

    print(f"Analyzing evaluation results from: {DEFAULT_JSON_FILE}")

    analysis_results = analyze_evaluation_results(DEFAULT_JSON_FILE)

    if analysis_results:
        print("\n--- Simplified Banner Evaluation Analysis (Counts & Accuracy per Extension) ---")
        # Use sort_dicts=False if using Python 3.8+
        try:
            pprint(analysis_results, indent=2, sort_dicts=False)
        except TypeError:
             pprint(analysis_results, indent=2)
        print("-----------------------------------------------------------------------------")
    else:
        print("Analysis could not be completed.") 