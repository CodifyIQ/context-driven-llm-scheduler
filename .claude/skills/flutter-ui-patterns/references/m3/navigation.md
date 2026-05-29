# M3 Navigation

Top-level navigation between sibling destinations (Home, Properties, Conversations…). Always use the M3 widgets — `NavigationBar` *not* `BottomNavigationBar`, `NavigationRail` *not* a custom side panel — so platform conventions, indicator styling, and accessibility come for free.

For form-factor selection logic and the `FormFactor` enum, see the **Adaptive Layout & Breakpoints** section in the main `SKILL.md`.

## NavigationBar — mobile

```dart
NavigationBar(
  selectedIndex: _currentIndex,
  indicatorColor: Theme.of(context).colorScheme.secondaryFixedDim,
  onDestinationSelected: _onDestinationSelected,
  destinations: const [
    NavigationDestination(
      icon: Icon(Icons.home_outlined),
      selectedIcon: Icon(Icons.home),
      label: 'Home',
    ),
  ],
)
```

## NavigationRail — tablet & desktop

```dart
NavigationRail(
  selectedIndex: _currentIndex,
  extended: ref.watch(navRailExpandedProvider),
  labelType: NavigationRailLabelType.none,
  onDestinationSelected: _onDestinationSelected,
  destinations: [
    NavigationRailDestination(
      icon: Icon(Icons.business_outlined),
      selectedIcon: Icon(Icons.business),
      label: Text('Properties'),
    ),
  ],
)
```

The extended/collapsed state is user-togglable and persisted in a Riverpod provider rather than derived directly from `FormFactor`. Default to `true` on expanded screens and `false` on tablet.

## Rules

- **Outlined icons for unselected, filled icons for selected.** This is the M3 convention and screen readers/visual scanning both rely on it.
- **Use `colorScheme.secondaryFixedDim` for the `NavigationBar` indicator** — it reads as a subtle highlight against the bar's surface color.
- **3–5 top-level destinations.** More than 5 → consider grouping; fewer than 3 → you probably don't need a nav bar at all.
- **Mirror routing.** When using `StatefulShellRoute`, the order of `destinations` must match the order of `StatefulShellBranch` entries. Document the branch index so future edits don't silently misroute taps.
