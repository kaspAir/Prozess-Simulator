<?php
/**
 * Reverse-Proxy fuer den Prozess-Simulator (Infomaniak Managed Hosting).
 * Identisches Muster wie hermespia.ch – nur der Ziel-Port unterscheidet sich.
 *
 * Eine Kopie pro Umgebung in den jeweiligen Web-Root (~/sites/<domain>/):
 *   ditwi.ch        -> 127.0.0.1:8010   (prod)
 *   test.ditwi.ch   -> 127.0.0.1:8011   (test)
 *   int.ditwi.ch    -> 127.0.0.1:8012   (integration)
 */
$path = $_SERVER['REQUEST_URI'];
$target = 'http://127.0.0.1:8010' . $path;

$ch = curl_init($target);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch, CURLOPT_HEADER, true);
curl_setopt($ch, CURLOPT_CUSTOMREQUEST, $_SERVER['REQUEST_METHOD']);
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    curl_setopt($ch, CURLOPT_POSTFIELDS, file_get_contents('php://input'));
}
$headers = [];
foreach (getallheaders() as $k => $v) {
    if (strtolower($k) !== 'host') $headers[] = "$k: $v";
}
$headers[] = 'X-Forwarded-Proto: https';
$headers[] = 'X-Real-IP: ' . $_SERVER['REMOTE_ADDR'];
curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
$response = curl_exec($ch);
$info = curl_getinfo($ch);
curl_close($ch);

$header_size = $info['header_size'];
$resp_headers = substr($response, 0, $header_size);
$body = substr($response, $header_size);
http_response_code($info['http_code']);
foreach (explode("\r\n", $resp_headers) as $h) {
    if (preg_match('/^(Content-Type|Set-Cookie|Location):/i', $h)) header($h);
}
echo $body;
