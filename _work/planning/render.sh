#!/bin/bash
#
# Render markdown planning docs with ANSI styling for terminal viewing
#

# ANSI color codes
BOLD='\033[1m'
DIM='\033[2m'
UNDERLINE='\033[4m'
RED='\033[31m'
GREEN='\033[32m'
YELLOW='\033[33m'
BLUE='\033[34m'
MAGENTA='\033[35m'
CYAN='\033[36m'
WHITE='\033[37m'
GRAY='\033[90m'
RESET='\033[0m'

# Box drawing characters
if [[ "$LANG" =~ UTF-8 ]] || [[ "$LC_ALL" =~ UTF-8 ]]; then
    TOP_LEFT='┌'
    TOP_RIGHT='┐'
    BOTTOM_LEFT='└'
    BOTTOM_RIGHT='┘'
    HORIZONTAL='─'
    VERTICAL='│'
    BULLET='•'
else
    TOP_LEFT='+'
    TOP_RIGHT='+'
    BOTTOM_LEFT='+'
    BOTTOM_RIGHT='+'
    HORIZONTAL='-'
    VERTICAL='|'
    BULLET='*'
fi

# Function to render a markdown file
render_markdown() {
    local file="$1"
    local in_code_block=false
    local code_lang=""

    while IFS= read -r line; do
        # Code blocks
        if [[ "$line" =~ ^\`\`\`(.*)$ ]]; then
            if $in_code_block; then
                in_code_block=false
                echo -e "${RESET}"
            else
                in_code_block=true
                code_lang="${BASH_REMATCH[1]}"
                echo -e "${DIM}${GRAY}"
            fi
            continue
        fi

        if $in_code_block; then
            echo -e "${DIM}${GRAY}  $line${RESET}"
            continue
        fi

        # Headers
        if [[ "$line" =~ ^#\ (.+)$ ]]; then
            echo ""
            echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════════════════════${RESET}"
            echo -e "${BOLD}${CYAN}${BASH_REMATCH[1]}${RESET}"
            echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════════════════════${RESET}"
            echo ""
        elif [[ "$line" =~ ^##\ (.+)$ ]]; then
            echo ""
            echo -e "${BOLD}${BLUE}${BASH_REMATCH[1]}${RESET}"
            echo -e "${BLUE}${HORIZONTAL}${HORIZONTAL}${HORIZONTAL}${HORIZONTAL}${HORIZONTAL}${HORIZONTAL}${HORIZONTAL}${HORIZONTAL}${HORIZONTAL}${HORIZONTAL}${RESET}"
        elif [[ "$line" =~ ^###\ (.+)$ ]]; then
            echo ""
            echo -e "${BOLD}${MAGENTA}${BASH_REMATCH[1]}${RESET}"
        elif [[ "$line" =~ ^####\ (.+)$ ]]; then
            echo -e "${YELLOW}${BASH_REMATCH[1]}${RESET}"

        # Bullet lists
        elif [[ "$line" =~ ^[\ ]*[-*]\ (.+)$ ]]; then
            indent="${line%%[-*]*}"
            content="${BASH_REMATCH[1]}"
            echo -e "${indent}${GREEN}${BULLET}${RESET} $content"

        # Numbered lists
        elif [[ "$line" =~ ^[\ ]*[0-9]+\.\ (.+)$ ]]; then
            echo -e "${GREEN}$line${RESET}"

        # Checkboxes
        elif [[ "$line" =~ ^[\ ]*-\ \[\ \]\ (.+)$ ]]; then
            indent="${line%%-*}"
            echo -e "${indent}${GRAY}☐${RESET} ${BASH_REMATCH[1]}"
        elif [[ "$line" =~ ^[\ ]*-\ \[x\]\ (.+)$ ]]; then
            indent="${line%%-*}"
            echo -e "${indent}${GREEN}☑${RESET} ${BASH_REMATCH[1]}"

        # Tables (simple detection)
        elif [[ "$line" =~ ^\|.+\|$ ]]; then
            echo -e "${DIM}${CYAN}$line${RESET}"

        # Horizontal rules
        elif [[ "$line" =~ ^---+$ ]] || [[ "$line" =~ ^\*\*\*+$ ]]; then
            echo -e "${GRAY}${HORIZONTAL}${HORIZONTAL}${HORIZONTAL}${HORIZONTAL}${HORIZONTAL}${HORIZONTAL}${HORIZONTAL}${HORIZONTAL}${HORIZONTAL}${HORIZONTAL}${HORIZONTAL}${HORIZONTAL}${HORIZONTAL}${HORIZONTAL}${HORIZONTAL}${HORIZONTAL}${HORIZONTAL}${HORIZONTAL}${HORIZONTAL}${HORIZONTAL}${RESET}"

        # Regular text
        else
            echo -e "$line"
        fi
    done < "$file"

    echo ""
}

# Main script
main() {
    local doc_dir="$(dirname "$0")"

    # If specific file provided, render it
    if [[ -n "$1" ]]; then
        if [[ -f "$doc_dir/$1" ]]; then
            render_markdown "$doc_dir/$1"
        elif [[ -f "$1" ]]; then
            render_markdown "$1"
        else
            echo -e "${RED}Error: File not found: $1${RESET}" >&2
            exit 1
        fi
        exit 0
    fi

    # Otherwise, show menu
    echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════════════════════${RESET}"
    echo -e "${BOLD}${CYAN}          o365-cli MVC Refactoring - Planning Documents            ${RESET}"
    echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════════════════════${RESET}"
    echo ""
    echo -e "${BOLD}Available documents:${RESET}"
    echo ""
    echo -e "  ${GREEN}0${RESET}. ${BOLD}Index${RESET} - Overview and quick links"
    echo -e "  ${GREEN}1${RESET}. ${BOLD}Architecture${RESET} - MVC structure proposal"
    echo -e "  ${GREEN}2${RESET}. ${BOLD}Consistent Options${RESET} - Standardized CLI flags"
    echo -e "  ${GREEN}3${RESET}. ${BOLD}Output Formats${RESET} - TUI vs Plain examples"
    echo -e "  ${GREEN}4${RESET}. ${BOLD}Migration Plan${RESET} - 8-week implementation guide"
    echo ""
    echo -e "${DIM}Usage:${RESET}"
    echo -e "  ${YELLOW}./render.sh${RESET}              ${DIM}# Show this menu${RESET}"
    echo -e "  ${YELLOW}./render.sh 00-index.md${RESET}  ${DIM}# Render specific doc${RESET}"
    echo -e "  ${YELLOW}./render.sh 1${RESET}            ${DIM}# Render by number (1-4)${RESET}"
    echo ""
    echo -e "${DIM}Or open directly:${RESET}"
    echo -e "  ${YELLOW}less 01-architecture.md${RESET}"
    echo -e "  ${YELLOW}bat 03-output-formats.md${RESET}  ${DIM}# If you have bat installed${RESET}"
    echo ""

    # If argument is a number, render that doc
    if [[ "$1" =~ ^[0-4]$ ]]; then
        case $1 in
            0) render_markdown "$doc_dir/00-index.md" ;;
            1) render_markdown "$doc_dir/01-architecture.md" ;;
            2) render_markdown "$doc_dir/02-consistent-options.md" ;;
            3) render_markdown "$doc_dir/03-output-formats.md" ;;
            4) render_markdown "$doc_dir/04-migration-plan.md" ;;
        esac
    fi
}

main "$@"
