import re
import os
import sys
from pypdf import PdfReader


books_directory = "/books"
text_directory = "/text"


def process_pdf(file_name: str) -> str:
    """
    Reads a specific PDF and writes the extracted text to a file.
    Returns the output file path as a string.

    :param file_name: The name of the PDF file to process.
    :return: The path of the output text file as a string.
    """
    file_path = os.path.join(books_directory, file_name)

    if not os.path.exists(file_path):
        print(f"File '{file_name}' not found in the books directory.")
        return ""

    try:
        reader = PdfReader(file_path)
        number_of_pages = len(reader.pages)
        print(f"Processing '{file_name}' with {number_of_pages} pages.")

        # Create an output file path
        output_file = os.path.join(text_directory, f"{file_name}.txt")
        with open(output_file, 'w') as f:
            for i in range(number_of_pages):
                page = reader.pages[i]
                text = page.extract_text()
                f.write(f"--- Page {i+1} ---\n{text}\n\n")
        print(f"Text written to {output_file}")

        return output_file

    except Exception as e:
        print(f"Error processing {file_name}: {e}")

        return ""


def remove_page_number_lines(output_file_path: str):
    """
    This function removes lines of the form "--- Page X ---".
    It modifies the file in place.

    :param output_file_path: The full path to the output .txt file.
    """
    if not os.path.exists(output_file_path):
        print(f"File '{output_file_path}' not found.")
        return

    with open(output_file_path, 'r') as file:
        lines = file.readlines()

    # Pattern to match lines like "--- Page 14 ---"
    page_pattern = re.compile(r'^--- Page \d+ ---$')

    # Filter out lines that match the pattern
    cleaned_lines = [
        line for line in lines if not page_pattern.match(line.strip())
        ]

    # Overwrite the file with the cleaned content
    with open(output_file_path, 'w') as file:
        file.writelines(cleaned_lines)

    print(f"Page number lines removed from {output_file_path}.")


def remove_page_number_with_blank_line(output_file_path: str) -> str:
    """
    This function removes lines that contain only
    an integer followed by a blank line.
    It modifies the file in place.

    :param output_file_path: The full path to the output .txt file.
    :return: The path to the modified output file.
    """
    # Read the file and identify lines to remove
    with open(output_file_path, 'r') as file:
        lines = file.readlines()

    # Pattern to match a line containing only an integer
    # (with optional spaces)
    # followed by a blank line
    number_pattern = re.compile(r'^\s*\d+\s*$')

    # List to hold cleaned lines
    cleaned_lines = []
    skip_next_line = False

    for i, line in enumerate(lines):
        if skip_next_line:
            skip_next_line = False
            continue

        # Check if the current line matches the
        # number pattern and the next line is blank
        if number_pattern.match(
            line.strip()
        ) and (i + 1 < len(lines) and lines[i + 1].strip() == ''):
            # Skip this line and the next blank line
            skip_next_line = True
        else:
            # If no match, add the line to the cleaned lines
            cleaned_lines.append(line)

    # Overwrite the file with the cleaned content
    with open(output_file_path, 'w') as file:
        file.writelines(cleaned_lines)

    print(
        f"Page #s followed by blank lines removed from {output_file_path}."
        )
    return output_file_path


def calculate_cost_without_free_limit(output_file_path: str):
    """
    :param output_file_path: The full path to the output .txt file.
    :return: The total cost of the character usage.
    """

    if not os.path.exists(output_file_path):
        print(f"File '{output_file_path}' not found.")
        return 0.0

    with open(output_file_path, 'r') as file:
        content = file.read()

    num_characters = len(content)
    print(f"Number of characters in {output_file_path}: {num_characters}")

    # Pricing model (US$0.000004 per character)
    price_per_character = 0.000004

    # Calculate the total cost
    total_cost = num_characters * price_per_character

    print(f"Total cost for processing: ${total_cost:.6f}")


def main():

    # file_name = input("Enter the PDF file name (with extension): ")

    output_file_path = process_pdf(pdf_filename)

    remove_page_number_lines(output_file_path)

    remove_page_number_with_blank_line(output_file_path)

    calculate_cost_without_free_limit(output_file_path)


if __name__ == "__main__":

    if len(sys.argv) < 2:
        print("Usage: python read.py <pdf_filename>")
        sys.exit(1)

    pdf_filename = sys.argv[1]

    main()
