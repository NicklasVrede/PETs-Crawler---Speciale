import os
import json

def create_evaluation_tables(evaluation_dir, output_file=None):
    """
    Create HTML tables with pre-filled data for manual evaluation
    
    Args:
        evaluation_dir: Directory containing the evaluation data
        output_file: Optional file path for HTML output (default is based on timestamp)
    """
    if not output_file:
        output_file = f"banner_evaluation.html"
    
    # Get all domains
    domains = [d for d in os.listdir(evaluation_dir) 
               if os.path.isdir(os.path.join(evaluation_dir, d)) 
               and not d.startswith('.')]
    
    # Start HTML document
    html = f'''<!DOCTYPE html>
<html>
<head>
    <title>Banner Detection Evaluation</title>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        table {{ border-collapse: collapse; margin-bottom: 30px; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; }}
        th {{ background-color: #f2f2f2; text-align: left; }}
        img {{ max-width: 800px; height: auto; }}
        .screenshot {{ text-align: center; }}
        .manual-input {{ background-color: #ffffcc; }}
        input[type="checkbox"] {{ transform: scale(1.5); margin-right: 10px; }}
        select {{ padding: 5px; min-width: 200px; }}
        textarea {{ width: 100%; height: 60px; }}
        .domain-header {{ background-color: #4CAF50; color: white; font-size: 1.2em; padding: 10px; }}
        .extension-header {{ background-color: #2196F3; color: white; }}
        .save-button {{ padding: 10px 20px; background-color: #4CAF50; color: white; 
                       border: none; cursor: pointer; font-size: 16px; margin: 20px 0; }}
    </style>
    <script>
        function setAllBannerStatus(value) {{
            const selects = document.getElementsByName('banner_status');
            for (let i = 0; i < selects.length; i++) {{
                selects[i].value = value;
            }}
        }}
        
        function toggleAll(checkboxName, checked) {{
            const checkboxes = document.getElementsByName(checkboxName);
            for (let i = 0; i < checkboxes.length; i++) {{
                checkboxes[i].checked = checked;
            }}
        }}
        
        function exportToJSON() {{
            // Get all form data
            const tables = document.querySelectorAll('table');
            const results = [];
            
            tables.forEach(table => {{
                const domainMatch = table.querySelector('.domain-info').textContent.match(/Domain: (.+)/);
                const domain = domainMatch ? domainMatch[1] : '';
                const extensionMatch = table.querySelector('.extension-info').textContent.match(/Extension: (.+)/);
                const extension = extensionMatch ? extensionMatch[1] : '';
                const visitMatch = table.querySelector('.visit-info').textContent.match(/Visit: (.+)/);
                const visit = visitMatch ? visitMatch[1] : '';
                
                // Get all manual inputs
                const pageLoaded = table.querySelector('input[name="page_loaded"]').checked;
                const noBannerPresent = table.querySelector('input[name="no_banner_present"]').checked;
                const notes = table.querySelector('textarea[name="notes"]').value;
                
                // Derive banner_present and banner_removed based on the checkbox
                const bannerPresent = !noBannerPresent;
                const bannerRemoved = false;
                const bannerStatus = noBannerPresent ? "no_banner" : "present";
                
                // Get automated data
                const automatedConclusion = table.querySelector('.automated-conclusion').textContent;
                const pageStatus = table.querySelector('.page-status').textContent;
                const htmlAnalysis = table.querySelector('.html-analysis').textContent;
                const screenshotAnalysis = table.querySelector('.screenshot-analysis').textContent;
                
                // Create result object
                const result = {{
                    domain,
                    extension,
                    visit,
                    automated: {{
                        conclusion: automatedConclusion.replace('Automated Conclusion: ', ''),
                        page_status: pageStatus.replace('Page Status: ', ''),
                        html_analysis: htmlAnalysis.replace('HTML Analysis: ', ''),
                        screenshot_analysis: screenshotAnalysis.replace('Screenshot Analysis: ', '')
                    }},
                    manual: {{
                        page_loaded: pageLoaded,
                        banner_status: bannerStatus,
                        banner_present: bannerPresent,
                        banner_removed: bannerRemoved,
                        notes
                    }}
                }};
                
                results.push(result);
            }});
            
            // Create and download JSON file
            const dataStr = JSON.stringify(results, null, 2);
            const dataUri = 'data:application/json;charset=utf-8,'+ encodeURIComponent(dataStr);
            const exportName = 'banner_evaluation_' + new Date().toISOString().slice(0, 10) + '.json';

            const linkElement = document.createElement('a');
            linkElement.setAttribute('href', dataUri);
            linkElement.setAttribute('download', exportName);
            linkElement.click();
        }}
    </script>
</head>
<body>
    <h1>Banner Detection Evaluation</h1>
    <p>Complete the following evaluation by checking the appropriate boxes for each screenshot.</p>
    <p>When finished, click the "Export Results" button at the bottom to save your evaluations.</p>
    
    <hr>
'''
    
    # Process each domain and extension
    table_count = 0
    
    for domain in sorted(domains):
        domain_dir = os.path.join(evaluation_dir, domain)
        
        # Get all extensions for this domain
        extensions = [e for e in os.listdir(domain_dir) 
                      if os.path.isdir(os.path.join(domain_dir, e))]
        
        # Add domain header
        html += f'<div class="domain-header">Domain: {domain}</div>\n'
        
        for extension in sorted(extensions):
            ext_dir = os.path.join(domain_dir, extension)
            
            # Look for overview file
            overview_file = os.path.join(ext_dir, f"{domain}_overview.json")
            if not os.path.exists(overview_file):
                continue
                
            with open(overview_file, 'r') as f:
                overview_data = json.load(f)
            
            # Process each visit
            for visit_id, visit_data in sorted(overview_data.get('visits', {}).items()):
                # Only process if the visit ID is 'visit1'
                if visit_id != "visit1":
                    continue
                
                # Find corresponding screenshots
                screenshot_files = [f for f in os.listdir(ext_dir) 
                                   if f.endswith(('.png', '.jpg')) and visit_id in f]
                
                if not screenshot_files:
                    continue
                
                # Use first screenshot
                screenshot_file = screenshot_files[0]
                screenshot_path = os.path.join(ext_dir, screenshot_file)
                
                # Make the path relative to the output file
                rel_screenshot_path = os.path.relpath(screenshot_path, os.path.dirname(os.path.abspath(output_file)))
                
                # Create a table for this screenshot
                html += f'''
<table id="table_{table_count}">
    <tr>
        <th class="domain-info">Domain: {domain}</th>
        <th class="extension-info">Extension: {extension}</th>
        <th class="visit-info">Visit: {visit_id}</th>
    </tr>
    <tr>
        <td colspan="3" class="screenshot">
            <img src="{rel_screenshot_path}" alt="Screenshot for {domain} with {extension}">
        </td>
    </tr>
    <tr>
        <td class="automated-conclusion">Automated Conclusion: {visit_data.get('conclusion', 'unknown')}</td>
        <td class="page-status">Page Status: {visit_data.get('page_status', 'unknown')}</td>
        <td>Reason: {', '.join(visit_data.get('reason', ['none']))}</td>
    </tr>
    <tr>
        <td class="html-analysis">HTML Analysis: {visit_data.get('html', 'unknown')}</td>
        <td class="screenshot-analysis">Screenshot Analysis: {visit_data.get('screenshot', 'unknown')}</td>
        <td></td>
    </tr>
    <tr class="manual-input">
        <td>Page Loaded Correctly? <input type="checkbox" name="page_loaded"></td>
        <td colspan="2">
            <input type="checkbox" name="no_banner_present"> No Banner Present
        </td>
    </tr>
    <tr class="manual-input">
        <td colspan="3">Notes: <textarea name="notes"></textarea></td>
    </tr>
</table>
'''
                table_count += 1
    
    # Add export button and close HTML
    html += '''
    <button class="save-button" onclick="exportToJSON()">Export Results</button>
    
</body>
</html>
'''
    
    # Write to file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"Created evaluation tables with {table_count} screenshots at {output_file}")
    return output_file

# Analysis function to calculate metrics after manual evaluation
def analyze_evaluation_results(json_file):
    """
    Analyze the evaluation results JSON file to calculate accuracy metrics
    based on banner presence detection.
    
    Args:
        json_file: Path to the exported JSON results file
    
    Returns:
        dict: Metrics including accuracy, false positives, false negatives for presence detection.
    """
    with open(json_file, 'r') as f:
        results = json.load(f)
    
    metrics = {
        "total_evaluations": len(results),
        "pages_loaded": 0,
        "banners_present_manual": 0,
        "automated_detection_accuracy": 0,
        "false_positives_detection": 0,
        "false_negatives_detection": 0,
        "by_extension": {}
    }
    
    for result in results:
        extension = result["extension"]
        
        # Initialize extension metrics if not already present
        if extension not in metrics["by_extension"]:
            metrics["by_extension"][extension] = {
                "total": 0,
                "correct_detection": 0,
                "false_positives_detection": 0,
                "false_negatives_detection": 0
            }
        
        # Count basic stats
        if result["manual"]["page_loaded"]:
            metrics["pages_loaded"] += 1
        
        if result["manual"]["banner_present"]:
            metrics["banners_present_manual"] += 1
        
        # Determine if automated conclusion correctly detected banner presence/absence
        automated_conclusion = result["automated"]["conclusion"]
        manual_banner_present = result["manual"]["banner_present"]
        
        metrics["by_extension"][extension]["total"] += 1
        
        # Simplified logic to determine correctness of *detection*
        is_correct_detection = False
        is_false_positive_detection = False
        is_false_negative_detection = False
        
        # Only evaluate on correctly loaded pages
        if result["manual"]["page_loaded"]:
            # Automated system indicated banner presence (removed or likely_removed)
            automated_detected_banner = automated_conclusion in ["removed", "likely_removed"]
            # Automated system indicated banner absence (not_removed or unknown)
            automated_missed_banner = automated_conclusion in ["not_removed", "unknown"]
            
            # Case 1: Manual=No Banner, Automated=No Banner -> Correct
            if not manual_banner_present and automated_missed_banner:
                is_correct_detection = True
            
            # Case 2: Manual=Banner Present, Automated=Banner Present -> Correct
            elif manual_banner_present and automated_detected_banner:
                is_correct_detection = True
            
            # Case 3: Manual=No Banner, Automated=Banner Present -> False Positive Detection
            elif not manual_banner_present and automated_detected_banner:
                is_false_positive_detection = True
            
            # Case 4: Manual=Banner Present, Automated=No Banner -> False Negative Detection
            elif manual_banner_present and automated_missed_banner:
                is_false_negative_detection = True
        
        if is_correct_detection:
            metrics["automated_detection_accuracy"] += 1
            metrics["by_extension"][extension]["correct_detection"] += 1
        
        if is_false_positive_detection:
            metrics["false_positives_detection"] += 1
            metrics["by_extension"][extension]["false_positives_detection"] += 1
        
        if is_false_negative_detection:
            metrics["false_negatives_detection"] += 1
            metrics["by_extension"][extension]["false_negatives_detection"] += 1
    
    # Calculate percentages
    valid_evals = metrics["pages_loaded"]
    if valid_evals > 0:
        metrics["accuracy_percentage"] = (metrics["automated_detection_accuracy"] / valid_evals) * 100
        metrics["fp_detection_percentage"] = (metrics["false_positives_detection"] / valid_evals) * 100
        metrics["fn_detection_percentage"] = (metrics["false_negatives_detection"] / valid_evals) * 100
    
    if metrics["total_evaluations"] > 0:
        metrics["loaded_percentage"] = (metrics["pages_loaded"] / metrics["total_evaluations"]) * 100
        
        for ext in metrics["by_extension"]:
            ext_total = metrics["by_extension"][ext]["total"]
            if ext_total > 0:
                metrics["by_extension"][ext]["accuracy_percentage"] = (metrics["by_extension"][ext]["correct_detection"] / ext_total) * 100
                metrics["by_extension"][ext]["fp_detection_percentage"] = (metrics["by_extension"][ext]["false_positives_detection"] / ext_total) * 100
                metrics["by_extension"][ext]["fn_detection_percentage"] = (metrics["by_extension"][ext]["false_negatives_detection"] / ext_total) * 100
    
    return metrics

if __name__ == "__main__":
    # Change this to your evaluation directory
    evaluation_dir = "evaluation_data"
    output_file = "banner_evaluation.html"
    create_evaluation_tables(evaluation_dir, output_file)
    
    print(f"\nAfter completing the manual evaluation, run the analysis script:")
    print(f"python analyze_evaluation.py banner_evaluation_YYYY-MM-DD.json")
