import json
from collections import defaultdict
import math # Import math for isnan check if needed later, though division by zero handled

def analyze_evaluation_results(json_filepath):
    """
    Analyzes the banner evaluation JSON file to calculate counts and
    accuracy metrics per extension, focusing on prediction correctness.

    Args:
        json_filepath (str): Path to the evaluation JSON file.

    Returns:
        dict: A dictionary containing aggregated metrics.
              Returns None if the file cannot be read or parsed.
    """
    try:
        with open(json_filepath, 'r') as f:
            results = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error reading or parsing JSON file {json_filepath}: {e}")
        return None

    metrics = {
        "total_evaluations": len(results),
        "by_extension": {}
    }

    # Add tracking for domains by extension
    domains_by_extension = defaultdict(set)

    for result in results:
        extension = result["extension"]
        automated_data = result["automated"]
        manual_data = result["manual"]
        domain = result.get("domain", "unknown_domain") # Get domain name

        # Initialize extension metrics if not present
        if extension not in metrics["by_extension"]:
            metrics["by_extension"][extension] = {
                "total_entries": 0,
                "automated_loaded": 0,
                # --- Descriptive Counts (Optional, can be removed if desired) ---
                "automated_conclusions": defaultdict(int),
                "manual_banner_present_counts": defaultdict(int), # Renamed for clarity
                "manual_page_loaded_counts": defaultdict(int), # Renamed for clarity
                # --- Confusion Matrix & Unknowns Lists (Banner Presence) ---
                "true_positives": [],  # TP: Auto removed, Manual false
                "true_negatives": [],  # TN: Auto not_removed, Manual true
                "false_positives": [], # FP: Auto removed, Manual true
                "false_negatives": [], # FN: Auto not_removed, Manual false
                "correct_unknowns": [], # CU: Auto unknown, Manual false
                "incorrect_unknowns": [], # IU: Auto unknown, Manual true
                # --- Load Accuracy ---
                "correctly_identified_loads": 0,
                "automated_load_accuracy_percentage": 0.0,
                # --- Banner Presence Accuracy Metrics ---
                "overall_accuracy_percentage": 0.0, # (TP+TN+CU) / (TP+TN+FP+FN+CU+IU)
                "precision_percentage": 0.0,        # TP / (TP+FP)
                "recall_percentage": 0.0,           # TP / (TP+FN)
                "f1_score_percentage": 0.0          # 2*(Prec*Rec)/(Prec+Rec)
            }

        ext_metrics = metrics["by_extension"][extension]
        ext_metrics["total_entries"] += 1

        # --- Process entries where automated system reported page as loaded ---
        if automated_data["page_status"] == "loaded":
            ext_metrics["automated_loaded"] += 1

            conclusion = automated_data.get("conclusion", "missing")
            manual_present = manual_data.get("banner_present", None)
            manual_loaded = manual_data.get("page_loaded", None)

            # --- Count Descriptive Stats (Optional) ---
            ext_metrics["automated_conclusions"][conclusion] += 1
            if manual_present is True:
                ext_metrics["manual_banner_present_counts"]["true"] += 1
            elif manual_present is False:
                ext_metrics["manual_banner_present_counts"]["false"] += 1
            else:
                ext_metrics["manual_banner_present_counts"]["unknown_or_missing"] += 1

            if manual_loaded is True:
                ext_metrics["manual_page_loaded_counts"]["true"] += 1
                # Check for Correctly Identified Load
                ext_metrics["correctly_identified_loads"] += 1
            elif manual_loaded is False:
                ext_metrics["manual_page_loaded_counts"]["false"] += 1
            else:
                ext_metrics["manual_page_loaded_counts"]["unknown_or_missing"] += 1
            # --- End Descriptive Stats ---


            # --- Assign to Confusion Matrix & Unknowns Lists for Banner Presence ---
            if manual_present is not None:
                automated_thinks_removed = conclusion in ["removed", "likely_removed"]
                automated_thinks_not_removed = conclusion == "not_removed"
                automated_is_unknown = conclusion == "unknown"
                has_baseline_keywords = "baseline_keywords" in automated_data and automated_data["baseline_keywords"]

                if automated_thinks_removed:
                    if manual_present is False:
                        ext_metrics["true_positives"].append(domain) # TP
                    elif manual_present is True:
                        ext_metrics["false_positives"].append(domain) # FP
                elif automated_thinks_not_removed:
                    if manual_present is True:
                        ext_metrics["true_negatives"].append(domain) # TN
                    elif manual_present is False:
                        ext_metrics["false_negatives"].append(domain) # FN
                elif automated_is_unknown:
                    if manual_present is False:
                        # Always correct when unknown + banner not present
                        ext_metrics["correct_unknowns"].append(domain) # CU
                    elif manual_present is True:
                        # When banner is present, "unknown" is only incorrect if we had keywords
                        if has_baseline_keywords:
                            ext_metrics["incorrect_unknowns"].append(domain) # IU - Had keywords but still said unknown
                        else:
                            # Banner present but no keywords - correct to say unknown
                            ext_metrics["true_negatives"].append(domain) # Count as TN if no keywords
            # --- End Confusion Matrix Assignment ---

            # Track this domain for the current extension
            domains_by_extension[extension].add(domain)

        # --- End processing for automated loaded pages ---

    # --- Calculate Final Metrics Post-Processing ---
    for ext, ext_metrics in metrics["by_extension"].items():
        # Convert defaultdicts to regular dicts for cleaner output (Optional Stats)
        ext_metrics["automated_conclusions"] = dict(ext_metrics["automated_conclusions"])
        ext_metrics["manual_banner_present_counts"] = dict(ext_metrics["manual_banner_present_counts"])
        ext_metrics["manual_page_loaded_counts"] = dict(ext_metrics["manual_page_loaded_counts"])

        # --- Calculate Load Accuracy ---
        total_automated_loaded = ext_metrics["automated_loaded"]
        if total_automated_loaded > 0:
            load_accuracy = (ext_metrics["correctly_identified_loads"] / total_automated_loaded) * 100
            ext_metrics["automated_load_accuracy_percentage"] = round(load_accuracy, 2)
        else:
            ext_metrics["automated_load_accuracy_percentage"] = 0.0

        # --- Calculate Banner Presence Metrics (incorporating Unknowns) ---
        tp_count = len(ext_metrics["true_positives"])
        tn_count = len(ext_metrics["true_negatives"])
        fp_count = len(ext_metrics["false_positives"])
        fn_count = len(ext_metrics["false_negatives"])
        cu_count = len(ext_metrics["correct_unknowns"]) # Correct Unknowns
        iu_count = len(ext_metrics["incorrect_unknowns"]) # Incorrect Unknowns

        # Total assessed includes all categories where manual eval was possible
        total_assessed = tp_count + tn_count + fp_count + fn_count + cu_count + iu_count
        # Total correct now includes Correct Unknowns
        total_correct = tp_count + tn_count + cu_count

        # Overall Accuracy
        if total_assessed > 0:
            # Use the updated definition of total_correct and total_assessed
            overall_acc = total_correct / total_assessed * 100
            ext_metrics["overall_accuracy_percentage"] = round(overall_acc, 2)
        else:
            ext_metrics["overall_accuracy_percentage"] = 0.0

        # Precision
        if (tp_count + fp_count) > 0:
            precision = tp_count / (tp_count + fp_count) * 100
            ext_metrics["precision_percentage"] = round(precision, 2)
        else:
            ext_metrics["precision_percentage"] = 0.0 # No positive predictions made

        # Recall (Sensitivity)
        if (tp_count + fn_count) > 0:
            # Note: Actual positives = TP + FN (doesn't include CU/IU by standard def)
            recall = tp_count / (tp_count + fn_count) * 100
            ext_metrics["recall_percentage"] = round(recall, 2)
        else:
            ext_metrics["recall_percentage"] = 0.0 # No actual positives in data

        # F1 Score
        precision_val = ext_metrics["precision_percentage"] / 100
        recall_val = ext_metrics["recall_percentage"] / 100
        if (precision_val + recall_val) > 0:
            f1 = 2 * (precision_val * recall_val) / (precision_val + recall_val) * 100
            ext_metrics["f1_score_percentage"] = round(f1, 2)
        else:
            ext_metrics["f1_score_percentage"] = 0.0

    # After processing all results, compare domain sets
    if "no_extension" in domains_by_extension and len(domains_by_extension) > 1:
        no_ext_domains = domains_by_extension["no_extension"]
        print(f"\n--- Domain Analysis ---")
        print(f"Domains used for 'no_extension': {len(no_ext_domains)}")
        
        for ext in domains_by_extension:
            if ext != "no_extension":
                ext_domains = domains_by_extension[ext]
                print(f"Domains used for '{ext}': {len(ext_domains)}")
                
                # Find domains unique to no_extension (missing from this extension)
                missing_domains = no_ext_domains - ext_domains
                if missing_domains:
                    print(f"  Domains in 'no_extension' but missing from '{ext}': {', '.join(sorted(missing_domains))}")
                
                # Find domains unique to this extension (missing from no_extension)
                extra_domains = ext_domains - no_ext_domains
                if extra_domains:
                    print(f"  Domains in '{ext}' but missing from 'no_extension': {', '.join(sorted(extra_domains))}")

    return metrics

# Example Usage (assuming the script is run directly)
if __name__ == "__main__":
    # Find the evaluation file relative to the script location
    import os
    script_dir = os.path.dirname(os.path.abspath(__file__))
    json_file = os.path.join(script_dir, 'banner_evaluation_2.json') # Assumes JSON is in the same dir
    json_file = os.path.normpath(json_file) # Clean up path separators

    if not os.path.exists(json_file):
         print(f"Error: Evaluation JSON file not found at expected location: {json_file}")
         # Try an alternative common location if needed
         alt_json_file = os.path.join(script_dir, '..', 'banner_system_eval', 'banner_evaluation_1.json')
         alt_json_file = os.path.normpath(alt_json_file)
         if os.path.exists(alt_json_file):
             print(f"Trying alternative location: {alt_json_file}")
             json_file = alt_json_file
         else:
             print(f"Could not find the evaluation file.")
             exit(1) # Exit if file not found


    analysis_results = analyze_evaluation_results(json_file)

    if analysis_results:
        print("\n--- Banner Evaluation Analysis (Accuracy Focused with Domains) ---")
        print(f"Total Evaluations Processed: {analysis_results['total_evaluations']}")
        print("-----------------------------------------------------------------")

        for ext, metrics in analysis_results['by_extension'].items():
            print(f"\nExtension: {ext}")
            print("===================================")

            # --- General & Load Metrics ---
            print("  Load Assessment:")
            print(f"    - Total Entries: {metrics['total_entries']}")
            print(f"    - Automated Reported Loaded: {metrics['automated_loaded']}")
            print(f"    - Correctly Identified Loads (Manual Check): {metrics['correctly_identified_loads']}")
            print(f"    - Automated Load Accuracy: {metrics['automated_load_accuracy_percentage']:.2f}%")
            print(f"    - Manual Page Loaded Counts: {dict(metrics['manual_page_loaded_counts'])}")


            print("\n  Banner Presence Prediction (vs Manual):")

            # --- Calculate counts for the summary (using updated logic) ---
            tp_count = len(metrics['true_positives'])
            tn_count = len(metrics['true_negatives'])
            fp_count = len(metrics['false_positives'])
            fn_count = len(metrics['false_negatives'])
            cu_count = len(metrics['correct_unknowns'])
            iu_count = len(metrics['incorrect_unknowns'])

            # Use updated definitions based on analysis function
            correct_banner_predictions = tp_count + tn_count + cu_count
            total_banner_assessed = tp_count + tn_count + fp_count + fn_count + cu_count + iu_count

            # --- Print the requested summary metric ---
            if total_banner_assessed > 0:
                 # This line now reflects the new definition of correctness
                 print(f"    - Overall Banner Prediction Correctness: {correct_banner_predictions} / {total_banner_assessed} instances")
            else:
                 print(f"    - Overall Banner Prediction Correctness: 0 / 0 instances (No comparable data)")


            # --- Confusion Matrix & Unknowns Breakdown ---
            print("    Prediction Breakdown (Count [Domains]):")
            # Helper function to format domain lists nicely
            def format_domain_list(domain_list):
                if not domain_list:
                    return "[]"
                return f"[{', '.join(domain_list)}]" # Show all for now

            print(f"      - True Positives (Removed Correctly):     {tp_count:>3} {format_domain_list(metrics['true_positives'])}")
            print(f"      - True Negatives (Not Removed Correctly): {tn_count:>3} {format_domain_list(metrics['true_negatives'])}")
            print(f"      - False Positives (Said Removed, Was Present): {fp_count:>3} {format_domain_list(metrics['false_positives'])}")
            print(f"      - False Negatives (Said Not Removed, Was Missing): {fn_count:>3} {format_domain_list(metrics['false_negatives'])}")
            print(f"      - Correct Unknowns (Said Unknown, Was Missing): {cu_count:>3} {format_domain_list(metrics['correct_unknowns'])}")
            print(f"      - Incorrect Unknowns (Said Unknown, Was Present): {iu_count:>3} {format_domain_list(metrics['incorrect_unknowns'])}")


            # --- Performance Metrics ---
            # Note: Precision/Recall/F1 are still based on TP/TN/FP/FN
            print("    Performance Metrics (based on Removed/Not_Removed predictions):")
            print(f"      - Overall Accuracy (incl. Unknowns): {metrics['overall_accuracy_percentage']:.2f}%") # Renamed label slightly
            print(f"      - Precision:        {metrics['precision_percentage']:.2f}%")
            print(f"      - Recall:           {metrics['recall_percentage']:.2f}%")
            print(f"      - F1 Score:         {metrics['f1_score_percentage']:.2f}%")


            # --- Optional Descriptive Stats ---
            print("    Descriptive Counts:")
            print(f"      - Automated Conclusions: {dict(metrics['automated_conclusions'])}")
            print(f"      - Manual Banner Present Counts: {dict(metrics['manual_banner_present_counts'])}")


            print("-----------------------------------")


        # Optional: Save to a new JSON file (now includes unknown lists)
        output_filename = "banner_analysis_with_unknowns.json"
        try:
            import json # Ensure json is imported if saving
            with open(output_filename, 'w') as outfile:
                json.dump(analysis_results, outfile, indent=2)
            print(f"\nAnalysis results (raw dictionary with unknowns) saved to {output_filename}")
        except IOError as e:
            print(f"Error saving analysis results to {output_filename}: {e}") 