import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../features/dashboard/presentation/dashboard_screen.dart';
import '../../features/market_detail/presentation/market_detail_screen.dart';
import '../../features/signals/presentation/signal_detail_screen.dart';
import '../../features/signals/presentation/signals_list_screen.dart';
import 'scaffold_with_nav.dart';

/// Two-tab shell (Dashboard / Signals). Signal detail is pushed on top of
/// the Signals branch, preserving the bottom nav.
final _rootKey = GlobalKey<NavigatorState>();
final _dashboardKey = GlobalKey<NavigatorState>();
final _signalsKey = GlobalKey<NavigatorState>();

final appRouter = GoRouter(
  navigatorKey: _rootKey,
  initialLocation: '/dashboard',
  routes: [
    StatefulShellRoute.indexedStack(
      builder: (context, state, shell) => ScaffoldWithNav(navigationShell: shell),
      branches: [
        StatefulShellBranch(
          navigatorKey: _dashboardKey,
          routes: [
            GoRoute(
              path: '/dashboard',
              builder: (context, state) => const DashboardScreen(),
              routes: [
                GoRoute(
                  path: 'market/:symbol',
                  builder: (context, state) => MarketDetailScreen(
                    symbol: state.pathParameters['symbol']!,
                  ),
                ),
              ],
            ),
          ],
        ),
        StatefulShellBranch(
          navigatorKey: _signalsKey,
          routes: [
            GoRoute(
              path: '/signals',
              builder: (context, state) => const SignalsListScreen(),
              routes: [
                GoRoute(
                  path: ':id',
                  builder: (context, state) {
                    final id = int.parse(state.pathParameters['id']!);
                    return SignalDetailScreen(signalId: id);
                  },
                ),
              ],
            ),
          ],
        ),
      ],
    ),
  ],
);
