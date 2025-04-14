export interface Response<T extends any | Error | null = any | Error | null> {
  body?: T;
  statusCode: number;
}
