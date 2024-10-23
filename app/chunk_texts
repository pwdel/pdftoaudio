#!/usr/bin/env python3

import os
import argparse


def split_text_by_sentence(text: str, chunk_size: int) -> list:
    """
    Splits text into chunks that end on a sentence boundary.
    Ensures no chunk exceeds the specified chunk_size.
    """
    chunks = []
    start = 0
    while start < len(text):
        # Get the next chunk of text up to the chunk_size
        end = min(start + chunk_size, len(text))

        # If we're not at the end of the text, find the last sentence boundary
        if end < len(text):
            while end > start and text[end] not in '.!?':
                end -= 1
            # Include the punctuation mark in the chunk
            end += 1

        # Add the chunk to the list
        chunks.append(text[start:end].strip())
        start = end

    return chunks


def split_text_file(input_text: str):
    # Get the base name of the input file without extension
    base_name = os.path.splitext(os.path.splitext(input_text)[0])[0]
    input_filepath = f'../text/{input_text}'
    output_dir = f'../text/{base_name}'

    # Create the output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Read the input text file
    with open(input_filepath, 'r', encoding='utf-8') as f:
        text = f.read()

    # Split the text into chunks of 4900 characters
    chunk_size = 4900
    chunks = split_text_by_sentence(text, chunk_size)

    # Write each chunk into its own file
    for idx, chunk in enumerate(chunks):
        chunk_filename = os.path.join(output_dir, f'{idx+1:02}.txt')
        with open(chunk_filename, 'w', encoding='utf-8') as chunk_file:
            chunk_file.write(chunk)

        # Check the file size in bytes
        file_size = os.path.getsize(chunk_filename)
        print(f"{chunk_filename} size: {file_size} bytes")

        # Print a warning if the file size exceeds 5000 bytes
        if file_size > 5000:
            print(f"Warning: {chunk_filename} exceeds 5000 bytes.")

    print("Splitting complete.")


if __name__ == "__main__":
    # Set up command line argument parsing
    parser = argparse.ArgumentParser(
        description='Split a large text file into smaller chunks.'
        )
    parser.add_argument(
        'input_text',
        type=str,
        help='Name of the input text file (with extension, e.g., .pdf.txt)'
        )

    # Parse the arguments
    args = parser.parse_args()

    # Call the function with the provided argument
    split_text_file(args.input_text)
