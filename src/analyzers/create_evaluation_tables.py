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
                const bannerStatus = table.querySelector('select[name="banner_status"]').value;
                const notes = table.querySelector('textarea[name="notes"]').value;
                
                // Derive banner_present and banner_removed from banner_status
                const bannerPresent = bannerStatus === "present_not_removed" || bannerStatus === "present_removed";
                const bannerRemoved = bannerStatus === "present_removed";
                
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
    
    <div>
        <h3>Bulk Actions:</h3>
        <button onclick="toggleAll('page_loaded', true)">Set All Pages Loaded</button>
        <button onclick="toggleAll('page_loaded', false)">Clear All Pages Loaded</button>
        <button onclick="setAllBannerStatus('no_banner')">Set All to No Banner</button>
        <button onclick="setAllBannerStatus('present_not_removed')">Set All to Banner Present (Not Removed)</button>
        <button onclick="setAllBannerStatus('present_removed')">Set All to Banner Present (Removed)</button>
    </div>
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
            Banner Status: 
            <select name="banner_status">
                <option value="no_banner">No Banner Present</option>
                <option value="present_not_removed">Banner Present (Not Removed)</option>
                <option value="present_removed">Banner Present (Removed)</option>
            </select>
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
    
    Args:
        json_file: Path to the exported JSON results file
    
    Returns:
        dict: Metrics including accuracy, false positives, false negatives
    """
    with open(json_file, 'r') as f:
        results = json.load(f)
    
    metrics = {
        "total_evaluations": len(results),
        "pages_loaded": 0,
        "banners_present": 0,
        "banners_removed": 0,
        "automated_accuracy": 0,
        "false_positives": 0,
        "false_negatives": 0,
        "by_extension": {}
    }
    
    for result in results:
        extension = result["extension"]
        
        # Initialize extension metrics if not already present
        if extension not in metrics["by_extension"]:
            metrics["by_extension"][extension] = {
                "total": 0,
                "correct": 0,
                "false_positives": 0,
                "false_negatives": 0
            }
        
        # Count basic stats
        if result["manual"]["page_loaded"]:
            metrics["pages_loaded"] += 1
        
        if result["manual"]["banner_present"]:
            metrics["banners_present"] += 1
            
        if result["manual"]["banner_removed"]:
            metrics["banners_removed"] += 1
        
        # Determine if automated conclusion was correct
        automated_conclusion = result["automated"]["conclusion"]
        manual_removed = result["manual"]["banner_removed"]
        
        metrics["by_extension"][extension]["total"] += 1
        
        # Simplified logic to determine correctness
        is_correct = False
        is_false_positive = False
        is_false_negative = False
        
        # Only evaluate on correctly loaded pages
        if result["manual"]["page_loaded"]:
            # Case 1: Banner present + not removed + conclusion "not_removed" = correct
            if result["manual"]["banner_present"] and not manual_removed and automated_conclusion in ["not_removed", "unknown"]:
                is_correct = True
                
            # Case 2: Banner present + removed + conclusion "removed" = correct
            elif result["manual"]["banner_present"] and manual_removed and automated_conclusion in ["removed", "likely_removed"]:
                is_correct = True
                
            # Case 3: No banner + conclusion "not_removed" = correct
            elif not result["manual"]["banner_present"] and automated_conclusion in ["not_removed", "unknown"]:
                is_correct = True
                
            # False positive: System said removed but it wasn't
            elif not manual_removed and automated_conclusion in ["removed", "likely_removed"]:
                is_false_positive = True
                
            # False negative: System missed that banner was removed
            elif manual_removed and automated_conclusion in ["not_removed", "unknown"]:
                is_false_negative = True
        
        if is_correct:
            metrics["automated_accuracy"] += 1
            metrics["by_extension"][extension]["correct"] += 1
        
        if is_false_positive:
            metrics["false_positives"] += 1
            metrics["by_extension"][extension]["false_positives"] += 1
            
        if is_false_negative:
            metrics["false_negatives"] += 1
            metrics["by_extension"][extension]["false_negatives"] += 1
    
    # Calculate percentages
    if metrics["total_evaluations"] > 0:
        metrics["accuracy_percentage"] = (metrics["automated_accuracy"] / metrics["total_evaluations"]) * 100
        metrics["loaded_percentage"] = (metrics["pages_loaded"] / metrics["total_evaluations"]) * 100
        
        for ext in metrics["by_extension"]:
            ext_total = metrics["by_extension"][ext]["total"]
            if ext_total > 0:
                metrics["by_extension"][ext]["accuracy_percentage"] = (metrics["by_extension"][ext]["correct"] / ext_total) * 100
    
    return metrics

if __name__ == "__main__":
    # Change this to your evaluation directory
    evaluation_dir = "evaluation_data"
    output_file = "banner_evaluation.html"
    create_evaluation_tables(evaluation_dir, output_file)
    
    print(f"\nAfter completing the manual evaluation, run the analysis script:")
    print(f"python analyze_evaluation.py banner_evaluation_YYYY-MM-DD.json")
