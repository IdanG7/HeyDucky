"""A simple buggy program for testing the debugger."""


def calculate_average(numbers):
    """Calculate the average of a list of numbers."""
    total = 0
    for num in numbers:
        total += num
    # Bug: should divide by len(numbers), not len(numbers) - 1
    return total / (len(numbers) - 1)


def process_data(data):
    """Process a list of data items."""
    results = []
    for item in data:
        if item > 0:
            results.append(item * 2)
        else:
            # Bug: appending None instead of 0
            results.append(None)
    return results


def main():
    """Main function with bugs to find."""
    numbers = [10, 20, 30, 40, 50]
    avg = calculate_average(numbers)
    print(f"Average: {avg}")

    data = [5, -3, 10, 0, -1, 7]
    processed = process_data(data)
    print(f"Processed: {processed}")

    # Bug: will crash when None is in the list
    total = sum(processed)
    print(f"Total: {total}")


if __name__ == "__main__":
    main()
