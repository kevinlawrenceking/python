import re

def extract_cf_errors(log_path, output_path=None):
    error_blocks = []
    current_block = []
    capturing = False

    # Keywords to ignore (case-insensitive)
    excluded_keywords = [
        'usersharepath',
        'cf_gen_fetch',
        'cal_root_dir',
        'ipn-cancelled.cfm'
    ]

    def should_skip(block_text):
        """Returns True if any excluded keyword is found in the block."""
        lower_text = block_text.lower()
        return any(keyword in lower_text for keyword in excluded_keywords)

    with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            if '"Error"' in line:
                if current_block:
                    full_block = '\n'.join(current_block).strip()
                    if not should_skip(full_block):
                        error_blocks.append(full_block)
                    current_block = []
                capturing = True
                current_block.append(line.strip())
            elif capturing:
                if line.startswith('"') and '"Error"' not in line:
                    capturing = False
                    full_block = '\n'.join(current_block).strip()
                    if not should_skip(full_block):
                        error_blocks.append(full_block)
                    current_block = []
                else:
                    if not line.lstrip().startswith("at "):
                        current_block.append(line.strip())

    if current_block:
        full_block = '\n'.join(current_block).strip()
        if not should_skip(full_block):
            error_blocks.append(full_block)

    if output_path:
        with open(output_path, 'w', encoding='utf-8') as out:
            for block in error_blocks:
                out.write(block + '\n\n')
    else:
        for block in error_blocks:
            print(block + '\n')

# Example usage
if __name__ == "__main__":
    extract_cf_errors(
        log_path="u:/docketwatch/python/error.log",
        output_path="u:/docketwatch/python/cleaned_errors.txt"
    )
