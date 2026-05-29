# M3 Menus

Source: [m3.material.io/components/menus](https://m3.material.io/components/menus) — overview, specs, guidelines.

A menu is a temporary surface that lets the user pick one option from a short list of choices anchored to a triggering element. Menus are not for primary content or long lists — if you find yourself reaching for either, you want a dialog, bottom sheet, or full page instead.

## When to use which menu type

Pick the menu variant based on *what the user is doing*, not which Flutter widget feels familiar.

| User intent | M3 variant | Flutter widget |
|-------------|-----------|----------------|
| Pick a value from a set (form field) | Dropdown menu | `DropdownMenu<T>` |
| Trigger one of several actions from a button | Menu (button-anchored) | `MenuAnchor` + `MenuItemButton` |
| Overflow / secondary actions on an app bar | Menu (icon-anchored) | `MenuAnchor` *or* `PopupMenuButton` |
| Right-click / long-press contextual actions | Context menu | `MenuAnchor` (opened programmatically at pointer) |
| Persistent top-level menus (desktop/web) | Menu bar | `MenuBar` + `SubmenuButton` |

Prefer `MenuAnchor` for new code — it follows M3 specs exactly, supports nested submenus, and gives you keyboard navigation for free. `PopupMenuButton` remains acceptable for simple app-bar overflow menus where the existing visual is fine; don't rewrite it just to swap APIs.

## Don't use a menu for…

- The **primary action** of a screen — that's a `FilledButton` or FAB.
- **More than ~10 items** — switch to a list page, bottom sheet, or searchable dropdown.
- **Destructive confirmation** — show an `AlertDialog` after the menu item is tapped; the menu itself should not be the confirm step.
- **Long descriptions per item** — menu items are single-line. If items need explanation, use a list with `ListTile` subtitles.

## Specs (M3 defaults — Flutter applies these automatically)

You generally don't hand-set these, but knowing the numbers helps you spot when a custom widget is drifting off-spec.

- Container shape: 4dp corner radius
- Container color: `colorScheme.surfaceContainer` at elevation level 2
- Min width: 112dp · Max width: 280dp
- Vertical padding inside container: 8dp top / 8dp bottom
- Item height: 48dp (single-line)
- Item horizontal padding: 12dp
- Leading icon: 24dp, 12dp gap to label
- Trailing element (shortcut text or icon): 24dp, right-aligned
- Divider: 1dp `colorScheme.outlineVariant`, used between groups
- Disabled state: label/icon at 38% `onSurface` opacity

## Content guidelines

- **4–6 items is the sweet spot.** Fewer and the menu is overkill; more and scanning gets hard.
- **Order by frequency or workflow**, not alphabetically — the user's most likely choice should be first.
- **Group with dividers** when items fall into clear categories (e.g., "view actions" vs. "destructive actions"). One divider above the destructive group is the most common pattern.
- **Be consistent with leading icons.** Either *all* items in a menu have a leading icon or none do — a half-iconned menu reads as broken. Trailing elements (keyboard shortcuts, chevrons for submenus) follow the same rule per column.
- **Labels are short and start with a verb**: "Edit", "Duplicate", "Move to trash" — not "Edit this item" or "You can edit".
- **Destructive items go last** and use `colorScheme.error` for the icon/label. See [`destructive-actions.md`](destructive-actions.md) for the full rule — error color applies to menu labels and dialog commit buttons, *not* to standalone icon-button triggers.
- **Submenus stay shallow** — one level deep. Deeper nesting frustrates pointer users and is unreachable on touch.

## Positioning and dismissal

`MenuAnchor` handles this for you, but be aware:

- The menu opens anchored to its trigger and flips above/below if it would overflow the viewport. Don't manually offset unless you have a layout reason.
- Menus dismiss on: outside tap, `Escape`, scroll of the underlying surface, or item activation. Don't trap focus or block dismissal.
- For context menus opened on long-press / right-click, open the `MenuAnchor` at the pointer location via its `MenuController`.

## Examples

```dart
// Button-anchored menu — actions on a single entity
MenuAnchor(
  builder: (context, controller, _) => IconButton(
    icon: const Icon(Icons.more_vert),
    tooltip: 'More actions',
    onPressed: () => controller.isOpen ? controller.close() : controller.open(),
  ),
  menuChildren: [
    MenuItemButton(
      leadingIcon: const Icon(Icons.edit_outlined),
      onPressed: _onEdit,
      child: const Text('Edit'),
    ),
    MenuItemButton(
      leadingIcon: const Icon(Icons.copy_outlined),
      onPressed: _onDuplicate,
      child: const Text('Duplicate'),
    ),
    const Divider(),
    MenuItemButton(
      leadingIcon: Icon(Icons.delete_outline, color: Theme.of(context).colorScheme.error),
      onPressed: _onDelete,
      child: Text(
        'Delete',
        style: TextStyle(color: Theme.of(context).colorScheme.error),
      ),
    ),
  ],
)

// Dropdown menu — picking a value in a form
DropdownMenu<UserTypeEnum>(
  initialSelection: UserTypeEnum.homeowner,
  label: const Text('User type'),
  onSelected: (value) => _onTypeChanged(value),
  dropdownMenuEntries: const [
    DropdownMenuEntry(value: UserTypeEnum.homeowner, label: 'Homeowner'),
    DropdownMenuEntry(value: UserTypeEnum.admin, label: 'Admin'),
  ],
)

// Submenu — only when grouping is genuinely clearer than a flat list
MenuAnchor(
  menuChildren: [
    MenuItemButton(onPressed: _onShare, child: const Text('Share')),
    SubmenuButton(
      menuChildren: [
        MenuItemButton(onPressed: _onExportPdf, child: const Text('PDF')),
        MenuItemButton(onPressed: _onExportCsv, child: const Text('CSV')),
      ],
      child: const Text('Export as…'),
    ),
  ],
  builder: (context, controller, _) => /* ... */,
)
```

## Accessibility

- Every `MenuItemButton` needs a clear text `child`; an icon-only menu item is unreadable to screen readers.
- Keyboard navigation (arrow keys, Enter, Escape) works out of the box with `MenuAnchor` — don't reimplement it.
- If a destructive item relies on color alone to signal danger, add an icon too — color is not a sufficient accessibility cue.
