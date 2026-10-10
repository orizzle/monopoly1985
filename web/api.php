<?php
// Online games for the browser port: a small relay that keeps, per game, the list of players and
// the shared key log. Every player's browser runs its own copy of the (deterministic) game; the
// log says which key the program receives at which keyboard poll, so all copies stay identical.
//
// Storage: one directory per game under MONOPOLY_DATA (default: <tmp>/monopoly-online):
//   meta.json   players, start state, horizon, control changes
//   keys.log    one JSON line per key: [poll, ascii, scan, as, hash]
//   events.log  one JSON line per event: start, chat, control
// Requests are POSTed as JSON: {"a": action, ...}; responses are JSON.

const MAX_SEATS = 4;           // the game takes 2 to 4 players
const OFFLINE_AFTER = 6;       // seconds without a request before a player counts as offline
const TAKEOVER_AFTER = 20;     // seconds offline before the host may play for someone
const ROOM_TTL = 6 * 3600;     // idle games are removed after this
const CODE_CHARS = 'ABCDEFGHJKLMNPQRSTUVWXYZ';

header('Content-Type: application/json');
header('Cache-Control: no-store');

function out($x, $status = 200) { http_response_code($status); echo json_encode($x); exit; }
function fail($err, $status = 400) { out(['ok' => false, 'error' => $err], $status); }

$dataDir = getenv('MONOPOLY_DATA') ?: (sys_get_temp_dir() . '/monopoly-online');
if (!is_dir($dataDir) && !@mkdir($dataDir, 0770, true)) fail('storage', 500);

if ($_SERVER['REQUEST_METHOD'] !== 'POST') fail('method', 405);
$raw = file_get_contents('php://input', false, null, 0, 1 << 20);
$req = json_decode($raw, true);
if (!is_array($req) || !isset($req['a'])) fail('request');

function validName($n) {
  return is_string($n) && $n === trim($n) && strlen($n) >= 1 && strlen($n) <= 10 && preg_match('/^[\x20-\x7E]+$/', $n);
}
function validCode($c) { return is_string($c) && preg_match('/^[A-Z]{4}$/', $c); }
function roomDir($code) { global $dataDir; return $dataDir . '/' . $code; }

// Opens a game and locks it for the rest of the request.
function openRoom($code) {
  if (!validCode($code)) fail('nogame', 404);
  $dir = roomDir($code);
  if (!is_dir($dir)) fail('nogame', 404);
  $lock = fopen("$dir/lock", 'c');
  flock($lock, LOCK_EX);
  $meta = json_decode(@file_get_contents("$dir/meta.json"), true);
  if (!$meta || !empty($meta['closed'])) fail('nogame', 404);
  return [$dir, $lock, $meta];
}
function saveMeta($dir, $meta) {
  file_put_contents("$dir/meta.tmp", json_encode($meta));
  rename("$dir/meta.tmp", "$dir/meta.json");
}
function appendLine($file, $x) { file_put_contents($file, json_encode($x) . "\n", FILE_APPEND); }
// Lines of a log from byte offset $off; returns [items, new offset].
function readFrom($file, $off) {
  $off = max(0, (int)$off);
  clearstatcache(true, $file);
  $size = @filesize($file);
  if ($size === false || $off >= $size) return [[], $off];
  $f = fopen($file, 'r'); fseek($f, $off);
  $data = stream_get_contents($f); fclose($f);
  $end = strrpos($data, "\n");
  if ($end === false) return [[], $off];
  $items = [];
  foreach (explode("\n", substr($data, 0, $end)) as $line) $items[] = json_decode($line, true);
  return [$items, $off + $end + 1];
}
function seatByToken($meta, $token) {
  foreach ($meta['seats'] as $i => $s) if (is_string($token) && hash_equals($s['token'], $token)) return $i;
  fail('notplayer', 403);
}
// Who types for seat $seat at keyboard poll $p (the host may play for an absent player).
function controller($meta, $seat, $p) {
  $by = $seat;
  foreach ($meta['ctl'] as $c) if ($c['seat'] === $seat && $c['from'] <= $p) $by = $c['by'];
  return $by;
}
function seatList($meta) {
  $now = time(); $list = [];
  foreach ($meta['seats'] as $i => $s)
    $list[] = ['name' => $s['name'], 'online' => $now - $s['seen'] < OFFLINE_AFTER,
               'away' => $now - $s['seen'], 'by' => controller($meta, $i, PHP_INT_MAX)];
  return $list;
}
function sweep() {
  global $dataDir;
  foreach (glob("$dataDir/[A-Z][A-Z][A-Z][A-Z]", GLOB_ONLYDIR) as $dir) {
    $m = @filemtime("$dir/meta.json");
    if ($m !== false && time() - $m > ROOM_TTL) { array_map('unlink', glob("$dir/*")); @rmdir($dir); }
  }
}
function newToken() { return bin2hex(random_bytes(16)); }

$a = $req['a'];

if ($a === 'create') {
  $name = $req['name'] ?? null;
  if (!validName($name)) fail('name');
  sweep();
  if (count(glob("$dataDir/[A-Z][A-Z][A-Z][A-Z]", GLOB_ONLYDIR)) >= 500) fail('busy', 503);
  for ($tries = 0; ; $tries++) {
    if ($tries > 50) fail('busy', 503);
    $code = '';
    for ($i = 0; $i < 4; $i++) $code .= CODE_CHARS[random_int(0, strlen(CODE_CHARS) - 1)];
    if (@mkdir(roomDir($code), 0770)) break;
  }
  $dir = roomDir($code);
  $token = newToken();
  $meta = ['code' => $code, 'created' => time(), 'started' => false, 'H' => -1, 'ctl' => [],
           'seats' => [['name' => $name, 'token' => $token, 'seen' => time()]]];
  touch("$dir/keys.log"); touch("$dir/events.log");
  saveMeta($dir, $meta);
  out(['ok' => true, 'code' => $code, 'token' => $token, 'seat' => 0]);
}

if ($a === 'join') {
  $name = $req['name'] ?? null;
  if (!validName($name)) fail('name');
  [$dir, $lock, $meta] = openRoom($req['code'] ?? '');
  $now = time();
  foreach ($meta['seats'] as $i => &$s) {
    if (strtoupper($s['name']) !== strtoupper($name)) continue;
    // The same name again: a player coming back (another tab, a reload, a new device) takes the
    // seat over once the old connection has gone quiet, or at once with the seat's own token.
    $own = is_string($req['token'] ?? null) && hash_equals($s['token'], $req['token']);
    if (!$own && $now - $s['seen'] < OFFLINE_AFTER) fail('nametaken', 409);
    $s['token'] = newToken(); $s['seen'] = $now;
    if ($meta['started'] && controller($meta, $i, PHP_INT_MAX) !== $i) {
      $c = ['seat' => $i, 'by' => $i, 'from' => $meta['H'] + 1];
      $meta['ctl'][] = $c;
      appendLine("$dir/events.log", ['t' => 'control'] + $c);
    }
    $token = $s['token'];
    unset($s);
    saveMeta($dir, $meta);
    out(['ok' => true, 'code' => $meta['code'], 'token' => $token, 'seat' => $i]);
  }
  unset($s);
  if ($meta['started']) fail('started', 409);
  if (count($meta['seats']) >= MAX_SEATS) fail('full', 409);
  $token = newToken();
  $meta['seats'][] = ['name' => $name, 'token' => $token, 'seen' => $now];
  saveMeta($dir, $meta);
  out(['ok' => true, 'code' => $meta['code'], 'token' => $token, 'seat' => count($meta['seats']) - 1]);
}

[$dir, $lock, $meta] = openRoom($req['code'] ?? '');
$me = seatByToken($meta, $req['token'] ?? null);
$meta['seats'][$me]['seen'] = time();

if ($a === 'leave') {
  if (!$meta['started']) {
    if ($me === 0) $meta['closed'] = true;                  // the host closes a game not yet started
    else array_splice($meta['seats'], $me, 1);
  } else {
    $meta['seats'][$me]['seen'] = 0;
  }
  saveMeta($dir, $meta);
  out(['ok' => true]);
}

if ($a === 'start') {
  if ($me !== 0) fail('nothost', 403);
  if ($meta['started']) fail('started', 409);
  if (count($meta['seats']) < 2) fail('players');
  $files = $req['files'] ?? [];
  if (!is_array($files) || count($files) > 50) fail('files');
  foreach ($files as $k => $v) if (!is_string($k) || strlen($k) > 12 || !is_string($v)) fail('files');
  $meta['started'] = true;
  appendLine("$dir/events.log", ['t' => 'start', 'seats' => array_column($meta['seats'], 'name'),
                                 'files' => (object)$files, 'load' => !empty($req['load'])]);
  saveMeta($dir, $meta);
  out(['ok' => true]);
}

if ($a === 'control') {                                   // the host plays for an absent player
  $seat = $req['seat'] ?? -1;
  if ($me !== 0) fail('nothost', 403);
  if (!$meta['started'] || !is_int($seat) || $seat < 1 || $seat >= count($meta['seats'])) fail('seat');
  if (time() - $meta['seats'][$seat]['seen'] < TAKEOVER_AFTER) fail('online', 409);
  if (controller($meta, $seat, PHP_INT_MAX) !== 0) {
    $c = ['seat' => $seat, 'by' => 0, 'from' => $meta['H'] + 1];
    $meta['ctl'][] = $c;
    appendLine("$dir/events.log", ['t' => 'control'] + $c);
  }
  saveMeta($dir, $meta);
  out(['ok' => true]);
}

if ($a === 'sync') {
  $result = ['ok' => true];
  // keys and horizon typed by this player (or by the host for an absent player)
  $keys = $req['keys'] ?? [];
  $h = $req['h'] ?? null;
  if ($keys || $h !== null) {
    if (!$meta['started'] || !is_array($keys) || count($keys) > 64) fail('keys');
    $H = $meta['H'];
    $lines = '';
    foreach ($keys as $k) {
      if (!is_array($k) || count($k) !== 5) fail('keys');
      [$p, $asc, $scan, $as, $hash] = $k;
      if (!is_int($p) || !is_int($asc) || !is_int($scan) || !is_int($as) || !is_int($hash)) fail('keys');
      if ($p <= $H) out(['ok' => false, 'error' => 'stale', 'H' => $H], 409);
      if ($as < 0 || $as >= count($meta['seats']) || controller($meta, $as, $p) !== $me) fail('notyours', 409);
      $lines .= json_encode([$p, $asc & 255, $scan & 255, $as, $hash]) . "\n";
      $H = $p;
    }
    if ($h !== null) {
      $has = $req['has'] ?? -1;
      if (!is_int($h) || !is_int($has) || $has < 0 || $has >= count($meta['seats'])) fail('h');
      if ($h > $H) {
        if (controller($meta, $has, $h) !== $me) fail('notyours', 409);
        $H = $h;
      }
    }
    if ($lines !== '') file_put_contents("$dir/keys.log", $lines, FILE_APPEND);
    $meta['H'] = $H;
  }
  $chat = $req['chat'] ?? null;
  if (is_string($chat) && trim($chat) !== '') {
    appendLine("$dir/events.log", ['t' => 'chat', 'seat' => $me, 'name' => $meta['seats'][$me]['name'],
                                   'text' => mb_substr(trim($chat), 0, 200)]);
  }
  saveMeta($dir, $meta);
  [$result['keys'], $result['ko']] = readFrom("$dir/keys.log", $req['ko'] ?? 0);
  [$result['events'], $result['eo']] = readFrom("$dir/events.log", $req['eo'] ?? 0);
  $result['H'] = $meta['H'];
  $result['started'] = $meta['started'];
  $result['seats'] = seatList($meta);
  $result['you'] = $me;
  out($result);
}

fail('action');
