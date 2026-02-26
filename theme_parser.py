import re
import json
from typing import List, Dict, Optional, Any

# --- Helpers ---------------------------------------------------------------


def split_prefix(line: str) -> (Optional[str], str):
    """
    Detects a leading marker like '#1:', 'R1:', '01:', '1:' etc.
    Returns (marker or None, remainder_of_line).
    """
    m = re.match(
        r"^\s*(?P<marker>(?:#|R|r)?\d{1,3}|(?:#R|R)\d{1,3})\s*[:.]?\s*(?P<rest>.*)$",
        line,
    )
    if m:
        marker = m.group("marker")
        rest = m.group("rest").strip()
        return marker, rest
    return None, line.strip()


def extract_parentheticals(line: str) -> (str, List[str]):
    """
    Pull out all (...) parenthetical groups.
    Returns the line with parentheticals removed, and list of the parenthetical contents.
    """
    parentheticals = re.findall(r"\(([^)]*)\)", line)
    cleaned = re.sub(r"\s*\([^)]*\)", "", line).strip()
    return cleaned, parentheticals


def find_title_and_artist(core: str) -> (str, Optional[str]):
    """
    Expect format like: '"Title" by Artist' or 'Title by Artist' or '"Title"'.
    Returns (title, artist_or_None).
    """
    # first try to split by ' by ' (case insensitive)
    parts = re.split(r"\s+by\s+", core, flags=re.I, maxsplit=1)
    if len(parts) == 2:
        title_part, artist_part = parts[0].strip(), parts[1].strip()
    else:
        title_part, artist_part = parts[0].strip(), None

    # Title might be quoted
    qm = re.search(r'"([^"]+)"', title_part)
    if qm:
        title = qm.group(1).strip()
    else:
        # otherwise take title as entire title_part
        title = title_part.strip().strip('"')

    return title, (artist_part.strip() if artist_part else None)


def parse_episode_tokens(
    parentheticals: List[str],
) -> (List[str], List[Dict[str, Any]], List[str]):
    """
    From the parenthetical list, extract token strings that look like episode specs
    (ep, eps, ep., eps., 'ep 1-12', 'eps 1-9, 11-12', 'ep 13-', etc.)
    Return:
      - episode_tokens: raw text snippets containing ep/eps
      - episode_ranges: normalized list of dicts like {"start":1,"end":12} or {"single":13} or {"raw":"13-??"}
      - other_notes: list of other parenthetical texts (not episodes)
    """
    episode_tokens = []
    other_notes = []
    episode_ranges = []

    for p in parentheticals:
        if re.search(r"\bep(s)?\b", p, flags=re.I):
            episode_tokens.append(p.strip())
            # try extracting numbers/ranges after ep/eps
            # allow forms: 'eps 1-12, 14-25', 'ep 13', 'eps 13-??', 'ep 13-'
            m = re.search(r"\bep(?:s)?\.?\s*([0-9\-,\?\s]+)", p, flags=re.I)
            if m:
                token = m.group(1).strip()
                # split by commas
                for chunk in [c.strip() for c in token.split(",") if c.strip()]:
                    if "-" in chunk:
                        start_str, end_str = [s.strip() for s in chunk.split("-", 1)]
                        # convert to ints where possible
                        try:
                            start = int(start_str)
                        except ValueError:
                            start = None
                        try:
                            end = (
                                int(end_str) if end_str and end_str.isdigit() else None
                            )
                        except ValueError:
                            end = None
                        episode_ranges.append(
                            {"start": start, "end": end, "raw": chunk}
                        )
                    else:
                        # single ep
                        try:
                            v = int(chunk)
                            episode_ranges.append({"single": v, "raw": chunk})
                        except ValueError:
                            episode_ranges.append({"raw": chunk})
            else:
                # couldn't parse numbers but keep raw
                episode_ranges.append({"raw": p})
        else:
            other_notes.append(p.strip())

        # convert empty lists to None
    if not episode_tokens:
        episode_tokens = None
    if not episode_ranges:
        episode_ranges = None
    if not other_notes:
        other_notes = None

    return episode_tokens, episode_ranges, other_notes


# --- Main parse function --------------------------------------------------


def parse_line(line: str) -> Dict[str, Any]:
    """
    Parse a single line into structured dict:
    {
      "marker": "#1" or "R1" or None,
      "title": "...",
      "artist": "...",
      "episode_tokens": [...],
      "episode_ranges": [...],
      "notes": [...],
      "raw": original_line
    }
    """
    raw = line.rstrip()
    marker, rest = split_prefix(raw)
    core, parentheticals = extract_parentheticals(rest)
    title, artist = find_title_and_artist(core)
    episode_tokens, episode_ranges, other_notes = parse_episode_tokens(parentheticals)

    return {
        "marker": marker,
        "title": title if title else None,
        "artist": artist,
        "episode_tokens": episode_tokens,  # raw ep-specs like 'eps 1-12, 14-25'
        "episode_ranges": episode_ranges,  # normalized ranges
        "notes": other_notes,  # other parenthetical content
        "parentheticals_raw": parentheticals,
        "raw": raw,
    }


def parse_text(text: str) -> List[Dict[str, Any]]:
    """
    Parse whole multiline text. Also tries to group numbered items under the most recent
    non-numbered header (i.e., when you have a title line followed by #1/#2 entries).
    Returns a flat list where each item may have 'parent_title' if grouped.
    """
    lines = [ln for ln in text.splitlines() if ln.strip() != ""]
    parsed = []
    last_non_numbered_index = None

    for ln in lines:
        item = parse_line(ln)
        parsed.append(item)

        # grouping heuristic:
        # if item has no marker (marker is None) -> it's a possible group header
        if not item["marker"]:
            last_non_numbered_index = len(parsed) - 1
            parsed[last_non_numbered_index]["is_group_header"] = True
        else:
            # if we have a prior non-numbered header, attach parent_title
            if last_non_numbered_index is not None:
                parsed[-1]["parent_title"] = parsed[last_non_numbered_index]["title"]

    return parsed


# --- Example usage --------------------------------------------------------

if __name__ == "__main__":
    # Example small snippet (you can replace example_text with your full giant list)
    example_text = """
"Tank!" by The Seatbelts (eps 1-25)
#1: "Chase the world" by May'n (eps 2-13)
#2: "Burst The Gravity" by ALTIMA (eps 14-23)
"Danzai no Hana~Guilty Sky" by Riyu Kosaka
#1: "The Real Folk Blues" by The Seatbelts feat. Mai Yamane (eps 1-12, 14-25)
#2: "Space Lion" by The Seatbelts (ep 13)
    """.strip()

    parsed = parse_text(example_text)
    print(json.dumps(parsed, indent=2, ensure_ascii=False))
