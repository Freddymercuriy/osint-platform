# Tor SOCKS proksi — faqat .onion manbalar uchun (onion_html ulagichi). Hostga port ochilmaydi:
# faqat compose tarmog'idagi backend `socks5h://tor:9050` orqali ulanadi.
FROM alpine:3.22
RUN apk add --no-cache tor \
 && mkdir -p /var/lib/tor && chown -R tor /var/lib/tor && chmod 700 /var/lib/tor
COPY torrc /etc/tor/torrc
USER tor
EXPOSE 9050
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD nc -z 127.0.0.1 9050 || exit 1
CMD ["tor", "-f", "/etc/tor/torrc"]
