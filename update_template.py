import sys

file_path = '/run/media/eibrahim11/programming/Django Project/un-official/Interactive_page_Demo/templates/content/subject_editor.html'
with open(file_path, 'r') as f:
    lines = f.readlines()

# Find the boundaries
sidebar_start = -1
sidebar_end = -1
modal_start = -1
modal_end = -1

for i, line in enumerate(lines):
    if '<div class="editor-sidebar">' in line:
        sidebar_start = i
    if '<div class="editor-modal-overlay" id="icInlinePanel" hidden>' in line:
        modal_start = i
    if '</div>' in line and i > modal_start and modal_end == -1:
        # Actually modal ends at </div> for editor-modal-overlay
        pass

# A more robust way to find the modal end
for i in range(modal_start, len(lines)):
    if '                            </div>' in line and '</form>' in lines[i-3] and '</div>' in lines[i-2]:
        pass

# The easiest way is to extract based on strings:
with open(file_path, 'r') as f:
    content = f.read()

modal_start_str = '                        <div class="editor-modal-overlay" id="icInlinePanel" hidden>'
modal_end_str = '                            </div>\n                        </div>\n'

modal_start_idx = content.find(modal_start_str)
modal_end_idx = content.find(modal_end_str, modal_start_idx) + len(modal_end_str)

modal_content = content[modal_start_idx:modal_end_idx]

# Remove modal from current position
new_content = content[:modal_start_idx] + content[modal_end_idx:]

# wrap sidebar in comment
sidebar_start_str = '                <div class="editor-sidebar">'
sidebar_end_str = '                </div>\n            </div>\n        </div>\n    </div>\n</section>'

s_idx = new_content.find(sidebar_start_str)
e_idx = new_content.find('                </div>\n            </div>', s_idx) + len('                </div>\n')

new_content = new_content[:s_idx] + '                {% comment %}\n' + new_content[s_idx:e_idx] + '                {% endcomment %}\n' + new_content[e_idx:]

# insert modal before </section>
section_idx = new_content.find('</section>')
new_content = new_content[:section_idx] + modal_content + new_content[section_idx:]

with open(file_path, 'w') as f:
    f.write(new_content)

print("Template updated successfully.")
