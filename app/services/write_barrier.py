def commit(self, records):
        committed = []
        try:
            with self.store.connection() as conn:
                cursor = conn.cursor()
                for record in records:
                    self.store.append_record(record, cursor=cursor)
                    committed.append(record.record_id)
                conn.commit()
            return committed
        except Exception as e:
            self.logger.error(f"Transaction failed: {e}")
            raise
