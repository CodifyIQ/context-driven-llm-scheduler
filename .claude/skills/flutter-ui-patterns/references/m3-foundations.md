# Material Design 3 — Foundations

The always-relevant M3 stuff: theme setup, color tokens, button hierarchy, and global rules. Read this any time you touch M3 UI. For component-specific guidance, see the routing table at the bottom.

## Theme Setup

```dart
ThemeData(
  useMaterial3: true,
  colorScheme: ColorScheme.fromSeed(
    seedColor: Color(0xFF033B53),
    primary: Color(0xFF033B53),
    secondary: Color(0xFF3e81b5),
  ),
)
```

## ColorScheme Tokens

Always use these — never hardcode hex color values. The token names encode *intent*, so swapping themes (light/dark, brand) doesn't require touching widget code.

```dart
colorScheme.surface                  // App bars, cards, dialogs
colorScheme.primary                  // Primary buttons, active states
colorScheme.primaryContainer         // Highlighted cards, selected items
colorScheme.onPrimaryContainer       // Text on primary container
colorScheme.secondary                // Secondary actions
colorScheme.secondaryFixedDim        // Navigation indicator color
colorScheme.error                    // Destructive commit actions (see m3/destructive-actions.md)
colorScheme.outline                  // Borders, dividers
colorScheme.onSurfaceVariant         // Secondary text, icons (incl. destructive icon buttons)
```

## Action Emphasis Hierarchy

Pick the component based on what the action *does*, not how important it feels.

| Component | Emphasis | Use for | Limit per screen |
|-----------|----------|---------|------------------|
| **FAB** | Highest | *Creating* something new (add, compose) | 1 |
| **FilledButton** | High | Primary *contextual* action (save, submit, next, confirm) | 1 per view/dialog |
| **FilledButton.tonal** | Medium | Supporting action alongside a filled button | Few |
| **OutlinedButton** | Low | Secondary actions (edit, cancel, alternative paths) | Multiple OK |
| **TextButton** | Lowest | Tertiary actions (skip, learn more, dismiss) | Multiple OK |

### FABs are for creation, not context

A FAB means "add a new thing" — not "save this form" or "go to next step." If the primary action operates on something already on screen (submit, next, confirm), use a `FilledButton`.

### One filled button per panel

Two equally prominent contextual actions → one `FilledButton`, the other `OutlinedButton` or `FilledButton.tonal`. Multiple filled buttons dilute emphasis and make the primary action ambiguous.

```dart
FloatingActionButton(onPressed: _onAdd, child: Icon(Icons.add))               // creation
FilledButton(onPressed: _onSubmit, child: Text('Submit'))                     // primary contextual
FilledButton.tonal(onPressed: _onAction, child: Text('Action'))               // medium support
OutlinedButton(onPressed: _onEdit, child: Text('Edit'))                       // secondary
TextButton(onPressed: _onSkip, child: Text('Skip'))                           // tertiary
```

## Global Rules

1. Always use M3 components — `NavigationBar` not `BottomNavigationBar`, `FilledButton` not `ElevatedButton`.
2. Use `ColorScheme` tokens — never hardcode hex values.
3. Outlined icons for unselected state, filled icons for selected.
4. Spacing in 4dp increments: 4, 8, 12, 16, 24, 32, 48.
5. Use default M3 transitions — avoid custom animations unless required.

---

## Component Reference Routing

When working with a specific component, read the matching file. Each file is scoped to one component so context stays cheap.

| Building / modifying… | Read |
|-----------------------|------|
| Menus, dropdowns, overflow, context menus | [`m3/menus.md`](m3/menus.md) |
| FABs (single or expandable) | [`m3/fabs.md`](m3/fabs.md) |
| `NavigationBar` / `NavigationRail` / shells | [`m3/navigation.md`](m3/navigation.md) |
| App bar actions, icon buttons, overflow placement | [`m3/app-bar.md`](m3/app-bar.md) |
| Delete / archive / any destructive flow (icon, menu item, dialog) | [`m3/destructive-actions.md`](m3/destructive-actions.md) |
