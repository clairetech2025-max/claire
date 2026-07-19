//go:build standalone

package main
import (
    "io"; "net/http"; "os"; "log"
)
func main() {
    // High-speed Ingest for 2GB+ files
    http.HandleFunc("/ingest", func(w http.ResponseWriter, r *http.Request) {
        f, _ := os.Create("/home/LuciusPrime/claire/silo_data/stream_" + r.Header.Get("X-Trace-ID"))
        defer f.Close()
        io.Copy(f, r.Body)
        w.Write([]byte("Sovereign Ingest Secure"))
    })
    log.Fatal(http.ListenAndServeTLS(":443", "/home/LuciusPrime/claire/certs/cert.pem", "/home/LuciusPrime/claire/certs/key.pem", nil))
}
