import os
import json
import argparse
from datetime import datetime

def create_html_evaluation_file(evaluation_dir, output_file=None):
    """
    Create HTML tables with pre-filled data for manual evaluation.

    Args:
        evaluation_dir: Directory containing the evaluation data (e.g., 'evaluation_data').
        output_file: Optional file path for HTML output (default is timestamped).
    """
    if not output_file:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"banner_evaluation_{timestamp}.html"

    # Ensure evaluation directory exists
    if not os.path.isdir(evaluation_dir):
        print(f"Error: Evaluation directory not found: {evaluation_dir}")
        return None

    # Get all domains
    try:
        domains = [d for d in os.listdir(evaluation_dir)
                   if os.path.isdir(os.path.join(evaluation_dir, d))
                   and not d.startswith('.')]
    except FileNotFoundError:
        print(f"Error: Could not list directories in {evaluation_dir}")
        return None
    except Exception as e:
        print(f"An error occurred listing domains: {e}")
        return None

    if not domains:
        print(f"No domain directories found in {evaluation_dir}")
        return None

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
        img {{ 
            max-width: 1200px; 
            width: 95%;
            height: auto; 
            display: block; 
            margin-left: auto; 
            margin-right: auto;
            cursor: pointer;
            transition: transform 0.3s ease;
        }}
        img:hover {{
            transform: scale(1.02);
        }}
        .screenshot {{ text-align: center; }}
        .manual-input {{ background-color: #ffffcc; }}
        input[type="checkbox"] {{ 
            transform: scale(3); 
            margin-right: 15px; 
            vertical-align: middle; 
            cursor: pointer;
        }}
        .checkbox-label {{
            display: inline-block;
            padding: 12px 16px;
            background-color: #f5f5f5;
            border-radius: 4px;
            margin-bottom: 15px;
            cursor: pointer;
            user-select: none;
            transition: background-color 0.2s;
            font-size: 16px;
            font-weight: bold;
            width: 90%;
        }}
        .checkbox-label:hover {{
            background-color: #e0e0e0;
        }}
        .checkbox-container {{
            margin-bottom: 20px;
        }}
        textarea {{ width: 98%; height: 60px; padding: 5px; }}
        .domain-header {{ background-color: #4CAF50; color: white; font-size: 1.2em; padding: 10px; margin-top: 20px; }}
        .extension-header {{ background-color: #2196F3; color: white; }}
        .save-button {{ padding: 10px 20px; background-color: #4CAF50; color: white;
                       border: none; cursor: pointer; font-size: 16px; margin: 20px 0; }}
        .info-cell {{ vertical-align: top; }}
        .analysis-label {{ font-weight: bold; }}
        
        /* Image modal */
        .modal {{
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            overflow: auto;
            background-color: rgba(0,0,0,0.9);
        }}
        .modal-content {{
            margin: auto;
            display: block;
            max-width: 90%;
            max-height: 90%;
        }}
        .modal-close {{
            position: absolute;
            top: 15px;
            right: 35px;
            color: #f1f1f1;
            font-size: 40px;
            font-weight: bold;
            cursor: pointer;
        }}
    </style>
    <script>
        function exportToJSON() {{
            const tables = document.querySelectorAll('table[id^="table_"]');
            const results = [];

            tables.forEach(table => {{
                const domainMatch = table.querySelector('.domain-info').textContent.match(/Domain: (.+)/);
                const domain = domainMatch ? domainMatch[1].trim() : '';
                const extensionMatch = table.querySelector('.extension-info').textContent.match(/Extension: (.+)/);
                const extension = extensionMatch ? extensionMatch[1].trim() : '';
                const visitMatch = table.querySelector('.visit-info').textContent.match(/Visit: (.+)/);
                const visit = visitMatch ? visitMatch[1].trim() : '';

                // Get manual inputs
                const pageLoadedInput = table.querySelector('input[name="page_loaded"]');
                const noBannerPresentInput = table.querySelector('input[name="no_banner_present"]');
                const notesInput = table.querySelector('textarea[name="notes"]');

                if (!pageLoadedInput || !noBannerPresentInput || !notesInput) {{
                    console.error(`Could not find all manual input elements for table ${{table.id}}`);
                    return; // Skip this table if elements are missing
                }}

                const pageLoaded = pageLoadedInput.checked;
                const noBannerPresent = noBannerPresentInput.checked;
                const notes = notesInput.value;

                // Derive banner_present and banner_removed based on the checkbox
                const bannerPresent = !noBannerPresent;
                // banner_removed is not directly captured here, set to false or derive if needed
                const bannerRemoved = false;
                const bannerStatus = noBannerPresent ? "no_banner" : "present";

                // Get automated data
                const automatedConclusionElem = table.querySelector('.automated-conclusion');
                const pageStatusElem = table.querySelector('.page-status');
                const htmlAnalysisElem = table.querySelector('.html-analysis');
                const screenshotAnalysisElem = table.querySelector('.screenshot-analysis');

                if (!automatedConclusionElem || !pageStatusElem || !htmlAnalysisElem || !screenshotAnalysisElem) {{
                    console.error(`Could not find all automated data elements for table ${{table.id}}`);
                    return; // Skip this table if elements are missing
                }}

                const automatedConclusion = automatedConclusionElem.textContent.replace('Automated Conclusion: ', '').trim();
                const pageStatus = pageStatusElem.textContent.replace('Page Status: ', '').trim();
                const htmlAnalysis = htmlAnalysisElem.textContent.replace('HTML Analysis: ', '').trim();
                const screenshotAnalysis = screenshotAnalysisElem.textContent.replace('Screenshot Analysis: ', '').trim();

                // Create result object
                const result = {{
                    domain,
                    extension,
                    visit,
                    automated: {{
                        conclusion: automatedConclusion,
                        page_status: pageStatus,
                        html_analysis: htmlAnalysis,
                        screenshot_analysis: screenshotAnalysis
                    }},
                    manual: {{
                        page_loaded: pageLoaded,
                        banner_status: bannerStatus,
                        banner_present: bannerPresent,
                        banner_removed: bannerRemoved, // Note: This is hardcoded based on current HTML
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
        
        // For image modal functionality
        document.addEventListener('DOMContentLoaded', function() {{
            // Create modal element
            const modal = document.createElement('div');
            modal.className = 'modal';
            modal.innerHTML = '<span class="modal-close">&times;</span><img class="modal-content" id="expandedImg">';
            document.body.appendChild(modal);
            
            const modalClose = modal.querySelector('.modal-close');
            const modalImg = modal.querySelector('#expandedImg');
            
            // Add click event to all screenshots
            document.querySelectorAll('.screenshot img').forEach(img => {{
                img.onclick = function() {{
                    modal.style.display = "block";
                    modalImg.src = this.src;
                }}
            }});
            
            // Close modal when clicking the x
            modalClose.onclick = function() {{
                modal.style.display = "none";
            }}
            
            // Close modal when clicking outside the image
            modal.onclick = function(event) {{
                if (event.target === modal) {{
                    modal.style.display = "none";
                }}
            }}
        }});
    </script>
</head>
<body>
    <h1>Banner Detection Evaluation</h1>
    <p>Complete the following evaluation by checking the appropriate boxes for each screenshot.</p>
    <p>When finished, click the "Export Results" button at the bottom to save your evaluations as a JSON file.</p>
    <p><strong>Tip:</strong> Click on any screenshot to view it in full size.</p>

    <hr>
'''

    # Process each domain and extension
    table_count = 0
    processed_screenshots = 0

    output_dir = os.path.dirname(os.path.abspath(output_file))

    for domain in sorted(domains):
        domain_dir = os.path.join(evaluation_dir, domain)
        if not os.path.isdir(domain_dir): continue

        # Get all extensions for this domain
        try:
            extensions = [e for e in os.listdir(domain_dir)
                          if os.path.isdir(os.path.join(domain_dir, e))]
        except Exception as e:
            print(f"Warning: Could not list extensions for {domain}: {e}")
            continue

        # Add domain header only if there are extensions to process
        domain_html_buffer = f'<div class="domain-header">Domain: {domain}</div>\n'
        domain_has_tables = False

        for extension in sorted(extensions):
            ext_dir = os.path.join(domain_dir, extension)
            if not os.path.isdir(ext_dir): continue

            # Look for overview file
            overview_file = os.path.join(ext_dir, f"{domain}_overview.json")
            if not os.path.exists(overview_file):
                # print(f"Debug: Overview file not found: {overview_file}")
                continue

            try:
                with open(overview_file, 'r', encoding='utf-8') as f:
                    overview_data = json.load(f)
            except json.JSONDecodeError:
                print(f"Warning: Could not decode JSON from {overview_file}")
                continue
            except Exception as e:
                print(f"Warning: Could not read {overview_file}: {e}")
                continue

            # Process each visit (currently only 'visit1')
            for visit_id, visit_data in sorted(overview_data.get('visits', {}).items()):
                if visit_id != "visit1": # Limit to visit1 for now as per original logic
                    continue

                # Find corresponding screenshot file (assuming one per visit/ext)
                screenshot_file = None
                try:
                    potential_files = [f for f in os.listdir(ext_dir)
                                       if f.endswith(('.png', '.jpg', '.jpeg')) and visit_id in f and extension in f]
                    if potential_files:
                        screenshot_file = potential_files[0] # Take the first match
                except Exception as e:
                    print(f"Warning: Could not list files in {ext_dir}: {e}")
                    continue

                if not screenshot_file:
                    # print(f"Debug: No screenshot found for {domain}/{extension}/{visit_id}")
                    continue

                screenshot_path = os.path.join(ext_dir, screenshot_file)
                if not os.path.exists(screenshot_path):
                     print(f"Warning: Screenshot file listed but not found: {screenshot_path}")
                     continue

                # Make the path relative to the output HTML file's directory
                try:
                    rel_screenshot_path = os.path.relpath(screenshot_path, output_dir)
                    # Replace backslashes for HTML compatibility
                    rel_screenshot_path = rel_screenshot_path.replace("\\", "/")
                except ValueError:
                     # Handle cases where paths are on different drives (Windows)
                     rel_screenshot_path = os.path.abspath(screenshot_path).replace("\\", "/")
                     print(f"Warning: Could not create relative path for {screenshot_path}. Using absolute path.")


                # Create a table for this screenshot
                domain_html_buffer += f'''
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
        <td class="info-cell">
            <span class="analysis-label">Automated Conclusion:</span> <span class="automated-conclusion">{visit_data.get('conclusion', 'unknown')}</span><br>
            <span class="analysis-label">Reason:</span> {', '.join(visit_data.get('reason', ['none']))}
        </td>
        <td class="info-cell">
            <span class="analysis-label">Page Status:</span> <span class="page-status">{visit_data.get('page_status', 'unknown')}</span><br>
            <span class="analysis-label">HTML Analysis:</span> <span class="html-analysis">{visit_data.get('html', 'unknown')}</span><br>
            <span class="analysis-label">Screenshot Analysis:</span> <span class="screenshot-analysis">{visit_data.get('screenshot', 'unknown')}</span>
        </td>
        <td class="manual-input info-cell">
            <div class="checkbox-container">
                <label class="checkbox-label">
                    <input type="checkbox" name="page_loaded">
                    Page Loaded Correctly?
                </label>
            </div>
            <div class="checkbox-container">
                <label class="checkbox-label">
                    <input type="checkbox" name="no_banner_present">
                    No Banner Present?
                </label>
            </div>
            Notes:<br> <textarea name="notes"></textarea>
        </td>
    </tr>
</table>
'''
                table_count += 1
                processed_screenshots += 1
                domain_has_tables = True

        # Only add the domain header and buffer if tables were generated for it
        if domain_has_tables:
            html += domain_html_buffer


    # Add export button and close HTML
    html += '''
    <button class="save-button" onclick="exportToJSON()">Export Results as JSON</button>

</body>
</html>
'''

    # Write to file
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"Created evaluation HTML with {processed_screenshots} screenshots at: {os.path.abspath(output_file)}")
        return output_file
    except Exception as e:
        print(f"Error writing HTML file {output_file}: {e}")
        return None

if __name__ == "__main__":
    # --- Configuration ---
    # Set the default path to your evaluation data directory here
    DEFAULT_EVALUATION_DIR = "evaluation_data"
    # Set a specific output file path, or leave as None for a timestamped name
    DEFAULT_OUTPUT_FILE = "banner_system_eval/banner_evaluation.html"
    # ---------------------

    print(f"Using evaluation directory: {DEFAULT_EVALUATION_DIR}")
    if DEFAULT_OUTPUT_FILE:
        print(f"Using output file: {DEFAULT_OUTPUT_FILE}")

    generated_file = create_html_evaluation_file(DEFAULT_EVALUATION_DIR, DEFAULT_OUTPUT_FILE)
