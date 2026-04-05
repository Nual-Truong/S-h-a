import hashlib


def compute_merkle_root(hash_list):
    if not hash_list:
        return hashlib.sha256(b"empty").hexdigest()

    current = [str(item) for item in hash_list]

    while len(current) > 1:
        if len(current) % 2 == 1:
            current.append(current[-1])

        next_level = []
        for i in range(0, len(current), 2):
            combined = f"{current[i]}|{current[i + 1]}"
            next_level.append(hashlib.sha256(combined.encode("utf-8")).hexdigest())
        current = next_level

    return current[0]
