<?php
/**
 * Reverse-Proxy fuer den Prozess-Simulator.
 *
 * Infomaniak Managed Hosting bietet kein root/nginx, aber PHP im Web-Root.
 * Dieses Skript leitet alle Requests an den lokalen Gunicorn weiter.
 *
 * Eine Kopie pro Umgebung im jeweiligen Web-Root ablegen und PORT anpassen:
 *   ditwi.ch        -> 8010   (prod)
 *   test.ditwi.ch   -> 8011   (test)
 *   int.ditwi.ch    -> 8012   (integration)
 */

$TARGET_HOST = '127.0.0.1';
$TARGET_PORT = 8010;

$uri = $_SERVER['REQUEST_URI'] ?? '/';
$url = 'http://' . $TARGET_HOST . ':' . $TARGET_PORT . $uri;

$method = $_SERVER['REQUEST_METHOD'] ?? 'GET';
$body   = file_get_contents('php://input');
$host   = $_SERVER['HTTP_HOST'] ?? 'ditwi.ch';

// Eingehende Header weiterreichen (Host/Content-Length setzt der Proxy/cURL selbst)
$headers = [];
foreach (getallheaders() as $name => $value) {
    $lower = strtolower($name);
    if ($lower === 'host' || $lower === 'content-length') {
        continue;
    }
    $headers[] = $name . ': ' . $value;
}
$headers[] = 'Host: ' . $host;
$headers[] = 'X-Forwarded-For: '   . ($_SERVER['REMOTE_ADDR'] ?? '');
$headers[] = 'X-Forwarded-Proto: https';
$headers[] = 'X-Forwarded-Host: '  . $host;

$ch = curl_init($url);
curl_setopt_array($ch, [
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_HEADER         => true,
    CURLOPT_CUSTOMREQUEST  => $method,
    CURLOPT_HTTPHEADER     => $headers,
    CURLOPT_FOLLOWLOCATION => false,
    CURLOPT_TIMEOUT        => 120,
    CURLOPT_CONNECTTIMEOUT => 10,
]);
if ($method !== 'GET' && $method !== 'HEAD') {
    curl_setopt($ch, CURLOPT_POSTFIELDS, $body);
}

$response = curl_exec($ch);

if ($response === false) {
    http_response_code(502);
    header('Content-Type: text/plain; charset=utf-8');
    echo "Bad Gateway: Backend (Prozess-Simulator auf :{$TARGET_PORT}) nicht erreichbar.";
    curl_close($ch);
    exit;
}

$header_size   = curl_getinfo($ch, CURLINFO_HEADER_SIZE);
$status        = curl_getinfo($ch, CURLINFO_HTTP_CODE);
$raw_headers   = substr($response, 0, $header_size);
$response_body = substr($response, $header_size);
curl_close($ch);

http_response_code($status);

// Backend-Header durchreichen; hop-by-hop / laengenbezogene Header filtern
$skip = ['transfer-encoding', 'connection', 'keep-alive', 'content-length'];
foreach (explode("\r\n", $raw_headers) as $line) {
    if (strpos($line, ':') === false) {
        continue;
    }
    list($name, $value) = explode(':', $line, 2);
    if (in_array(strtolower(trim($name)), $skip, true)) {
        continue;
    }
    header(trim($name) . ': ' . trim($value), false);
}

echo $response_body;
