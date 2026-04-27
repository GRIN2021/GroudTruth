#!/usr/bin/env python3
import argparse
import bisect
import collections
import importlib.util
import json
import re
import subprocess
from pathlib import Path


def load_blocks_pb2(path):
    spec = importlib.util.spec_from_file_location("blocks_pb2_dynamic", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def merge_ranges(ranges):
    ranges = sorted(ranges)
    merged = []
    for start, end in ranges:
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return [(start, end) for start, end in merged]


def in_ranges(addr, ranges, starts):
    idx = bisect.bisect_right(starts, addr) - 1
    if idx >= 0:
        start, end = ranges[idx]
        return start <= addr < end
    return False


def parse_groundtruth(blocks_pb2, gt_path):
    module = blocks_pb2.module()
    with open(gt_path, "rb") as f:
        module.ParseFromString(f.read())

    gt_inst_addrs = set()
    covered_ranges = []
    padding_ranges = []
    for func in module.fuc:
        for bb in func.bb:
            for inst in bb.instructions:
                gt_inst_addrs.add(int(inst.va))
            va = int(bb.va)
            size = int(bb.size)
            padding = int(bb.padding)
            covered_end = va + size - padding
            if covered_end > va:
                covered_ranges.append((va, covered_end))
            if padding > 0:
                pad_start = covered_end
                pad_end = va + size
                if pad_end > pad_start:
                    padding_ranges.append((pad_start, pad_end))

    covered_ranges = merge_ranges(covered_ranges)
    padding_ranges = merge_ranges(padding_ranges)
    return gt_inst_addrs, covered_ranges, padding_ranges


def parse_objdump_instructions(binary_path):
    result = subprocess.run(
        ["objdump", "-d", "-j", ".text", str(binary_path)],
        capture_output=True,
        text=True,
        check=True,
    )
    inst_re = re.compile(r"^\s*([0-9a-fA-F]+):\s+((?:[0-9a-fA-F]{2}\s)+)\s*(.*)$")
    instructions = []
    for line in result.stdout.splitlines():
        match = inst_re.match(line)
        if not match:
            continue
        addr = int(match.group(1), 16)
        bytes_field = match.group(2).strip()
        asm = match.group(3).strip()
        if not asm:
            continue
        size = len(bytes_field.split())
        instructions.append((addr, size, asm))
    return instructions


def merge_unseen_ranges(unseen):
    if not unseen:
        return []
    ranges = []
    start = unseen[0][0]
    end = unseen[0][0] + unseen[0][1]
    count = 1
    sample = [unseen[0][2]]
    for addr, size, asm in unseen[1:]:
        if addr == end:
            end = addr + size
            count += 1
            if len(sample) < 3:
                sample.append(asm)
        else:
            ranges.append((start, end, count, sample))
            start = addr
            end = addr + size
            count = 1
            sample = [asm]
    ranges.append((start, end, count, sample))
    return ranges


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", required=True)
    parser.add_argument("--groundtruth", required=True)
    parser.add_argument("--blocks-pb2", required=True)
    parser.add_argument("--out-prefix", required=True)
    args = parser.parse_args()

    binary = Path(args.binary)
    groundtruth = Path(args.groundtruth)
    out_prefix = Path(args.out_prefix)
    blocks_pb2 = load_blocks_pb2(args.blocks_pb2)

    gt_inst_addrs, covered_ranges, padding_ranges = parse_groundtruth(blocks_pb2, groundtruth)
    covered_starts = [start for start, _ in covered_ranges]
    padding_starts = [start for start, _ in padding_ranges]

    obj_insts = parse_objdump_instructions(binary)
    unseen = [(addr, size, asm) for addr, size, asm in obj_insts if addr not in gt_inst_addrs]
    unseen_ranges = merge_unseen_ranges(unseen)

    instruction_category_counts = collections.Counter()
    range_category_counts = collections.Counter()
    instruction_examples = {"padding": [], "outside_gt_coverage": []}
    range_examples = {"padding": [], "outside_gt_coverage": []}

    for addr, size, asm in unseen:
        if in_ranges(addr, padding_ranges, padding_starts):
            category = "padding"
        else:
            category = "outside_gt_coverage"
        instruction_category_counts[category] += 1
        if len(instruction_examples[category]) < 20:
            instruction_examples[category].append({"addr": hex(addr), "size": size, "asm": asm})

    unseen_range_items = []
    for start, end, inst_count, sample_asm in unseen_ranges:
        if in_ranges(start, padding_ranges, padding_starts):
            category = "padding"
        else:
            category = "outside_gt_coverage"
        range_category_counts[category] += 1
        item = {
            "start": hex(start),
            "end": hex(end),
            "inst_count": inst_count,
            "category": category,
            "sample_asm": sample_asm,
        }
        unseen_range_items.append(item)
        if len(range_examples[category]) < 20:
            range_examples[category].append(item)

    unseen_ratio = len(unseen) / len(gt_inst_addrs) if gt_inst_addrs else 0.0
    summary = {
        "binary": str(binary),
        "groundtruth": str(groundtruth),
        "objdump_real_instruction_count": len(obj_insts),
        "groundtruth_instruction_count": len(gt_inst_addrs),
        "unseen_instruction_count": len(unseen),
        "unseen_ratio_over_groundtruth": unseen_ratio,
        "covered_range_count": len(covered_ranges),
        "padding_range_count": len(padding_ranges),
        "unseen_contiguous_range_count": len(unseen_ranges),
        "instruction_category_counts": dict(instruction_category_counts),
        "range_category_counts": dict(range_category_counts),
        "instruction_examples": instruction_examples,
        "range_examples": range_examples,
        "unseen_ranges": unseen_range_items,
    }

    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    json_path = out_prefix.with_suffix(".summary.json")
    txt_path = out_prefix.with_suffix(".summary.txt")
    with open(json_path, "w") as f:
        json.dump(summary, f, indent=2)
    with open(txt_path, "w") as f:
        f.write(f"binary: {binary}\n")
        f.write(f"groundtruth: {groundtruth}\n")
        f.write(f"objdump_real_instruction_count: {len(obj_insts)}\n")
        f.write(f"groundtruth_instruction_count: {len(gt_inst_addrs)}\n")
        f.write(f"unseen_instruction_count: {len(unseen)}\n")
        f.write(f"unseen_ratio_over_groundtruth: {unseen_ratio:.12f}\n")
        f.write(f"unseen_contiguous_range_count: {len(unseen_ranges)}\n")
        f.write("\n[instruction_category_counts]\n")
        for key, value in instruction_category_counts.items():
            f.write(f"{key}: {value}\n")
        f.write("\n[range_category_counts]\n")
        for key, value in range_category_counts.items():
            f.write(f"{key}: {value}\n")
        f.write("\n[range_examples]\n")
        for key, items in range_examples.items():
            f.write(f"{key}:\n")
            for item in items:
                f.write(f"  {item['start']}-{item['end']} inst_count={item['inst_count']} sample={item['sample_asm']}\n")
        f.write("\n[all_unseen_ranges]\n")
        for item in unseen_range_items:
            f.write(f"{item['start']}-{item['end']} {item['category']} inst_count={item['inst_count']}\n")

    print(json.dumps({
        "summary_txt": str(txt_path),
        "summary_json": str(json_path),
        "unseen_instruction_count": len(unseen),
        "unseen_ratio_over_groundtruth": unseen_ratio,
        "instruction_category_counts": dict(instruction_category_counts),
        "range_category_counts": dict(range_category_counts),
    }, indent=2))


if __name__ == "__main__":
    main()
