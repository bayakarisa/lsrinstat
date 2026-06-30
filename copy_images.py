#!/usr/bin/env python3
"""
Copy and convert images from bookdown to PreTeXt generated-assets directory.
This script prepares images for the PreTeXt build process.

Image sources (in priority order):
1. bookdown/_bookdown_files/lsr_files/figure-html/ - knitr-generated PNGs (git-tracked)
2. bookdown/img/ - static screenshots and hand-drawn figures (PNG, JPG, EPS)
"""

import re
import shutil
import subprocess
from pathlib import Path

# Mapping from knitr chunk names to the image names expected by the PreTeXt source.
# Knitr output files are named "{chunk_name}-{plot_number}.png"; we use plot number 1.
# Keys are lowercase knitr chunk names; values are the target filenames (without extension).
KNITR_RENAMES = {
    # ANOVA chapter - chunk names differ from expected image names
    "anovavara": "anova1",
    "anovavarb": "anova2",
    # Chi-square chapter
    "goftest": "chisquaretestdist",
    # Case differences
    "zeppo": "Zeppo",
    "aflsd": "aflSD",
    # T-test chapter
    "harpohistanastasia": "HarpoAnastasia",
    "harpohistbernadette": "HarpoBernadette",
    "ttesthyp": "studentTestHyp",
    "ttesthyp2": "welchTestHyp",
    "ttesthyp_onesample": "oneSampleTTestHyp",
    # Estimation chapter
    "lineplotci": "CI_lineplot",
    "bargraphci": "CI_plotmeans",
    # Graphics chapter
    "pch": "pchvalues",
    # QQ-plot mappings (ttest chapter)
    "qq1a": "qqNormalHist",
    "qq1b": "qqNormalPlot",
    "qq2a": "qqSkewedHist",
    "qq2b": "qqSkewedPlot",
    "qq2c": "qqHeavyTailedHist",
    "qq2d": "qqHeavyTailedPlot",
    # Paired t-test figures
    "pairedta": "pairedMeans",
    "pairedtb": "pairedScatterplot",
    "pairedtc": "pairedHist",
}


def main():
    # Define paths
    script_dir = Path(__file__).parent
    bookdown_img = script_dir / "bookdown" / "img"
    knitr_figures = (
        script_dir
        / "bookdown"
        / "_bookdown_files"
        / "lsr_files"
        / "figure-html"
    )
    # Put generated images in pretext/assets/generated/ directory.
    # This matches the publication.ptx configuration where "external" is ../assets
    # and source files reference images as source="generated/<name>.png".
    pretext_assets = script_dir / "pretext" / "assets" / "generated"

    print("Preparing images for PreTeXt book...")
    print(f"Knitr figures: {knitr_figures}")
    print(f"Static images: {bookdown_img}")
    print(f"Target:        {pretext_assets}")

    # Create assets/generated directory
    pretext_assets.mkdir(parents=True, exist_ok=True)

    # Check if ImageMagick convert is available
    convert_available = shutil.which("convert") is not None

    if convert_available:
        print("ImageMagick found - will convert EPS to PNG")
    else:
        print("ImageMagick not found - will only copy existing PNG/JPG files")

    images_copied = 0
    images_converted = 0

    # -----------------------------------------------------------------------
    # Step 1: Copy from knitr figure output (highest priority).
    # Files are named "{chunk_name}-{N}.png"; we only take the first plot (N=1).
    # -----------------------------------------------------------------------
    if knitr_figures.is_dir():
        # Pattern matches "{chunk_name}-{plot_number}.png".
        # The greedy (.+) correctly captures everything up to the *last* hyphen-number
        # group because the end anchor ensures \d+ consumes only the trailing number.
        pattern = re.compile(r"^(.+)-(\d+)\.png$")
        for png_file in sorted(knitr_figures.glob("*.png")):
            m = pattern.match(png_file.name)
            if not m:
                continue
            chunk_name, plot_num = m.group(1), m.group(2)
            # Only take the first plot for each chunk
            if plot_num != "1":
                continue

            # Look up renamed target; fall back to the chunk name itself
            target_stem = KNITR_RENAMES.get(chunk_name.lower(), chunk_name)
            target_file = pretext_assets / f"{target_stem}.png"

            shutil.copy2(png_file, target_file)
            images_copied += 1
            if target_stem != chunk_name:
                print(f"  Copied (renamed): {png_file.name} -> {target_stem}.png")
            else:
                print(f"  Copied: {png_file.name} -> {target_stem}.png")
    else:
        print(f"  Warning: knitr figures directory not found: {knitr_figures}")

    # -----------------------------------------------------------------------
    # Step 2: Copy static PNG and JPG files from bookdown/img.
    # Skip defunct images and skip files that were already copied from knitr.
    # -----------------------------------------------------------------------
    for img_file in bookdown_img.rglob("*"):
        if not img_file.is_file():
            continue
        if "defunct_images" in str(img_file):
            continue
        # Only handle raster image formats here; EPS files are converted in Step 3.
        if img_file.suffix.lower() not in (".png", ".jpg", ".jpeg"):
            continue

        target_file = pretext_assets / img_file.name
        # Don't overwrite images already placed from knitr output
        if target_file.exists():
            continue

        shutil.copy2(img_file, target_file)
        images_copied += 1
        print(f"  Copied: {img_file.name}")

    # -----------------------------------------------------------------------
    # Step 3: Convert EPS files to PNG using ImageMagick (fallback for images
    # that are only available in EPS format and were not covered above).
    # -----------------------------------------------------------------------
    if convert_available:
        for eps_file in bookdown_img.rglob("*.eps"):
            if "defunct_images" in str(eps_file):
                continue

            base_name = eps_file.stem
            target_file = pretext_assets / f"{base_name}.png"

            # Skip if already provided by knitr output or static copy
            if target_file.exists():
                continue

            try:
                subprocess.run(
                    [
                        "convert",
                        "-density", "300",
                        "-quality", "90",
                        str(eps_file),
                        str(target_file),
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                images_converted += 1
                print(f"  Converted: {base_name}.eps -> {base_name}.png")
            except subprocess.CalledProcessError as e:
                print(f"  Warning: Failed to convert {eps_file.name}: {e}")
            except Exception as e:
                print(f"  Warning: Error processing {eps_file.name}: {e}")

    # Summary
    total_images = len(list(pretext_assets.glob("*")))
    print(f"\nComplete!")
    print(f"  Copied:    {images_copied} image files")
    print(f"  Converted: {images_converted} EPS files")
    print(f"  Total images in assets/generated: {total_images}")

    if total_images == 0:
        print("\nWARNING: No images were created. Images may not render correctly.")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
