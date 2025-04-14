import { Request, Response } from "./index.js";

export interface Controller<T, R> {
  handle(request: Request<T>): Promise<Response<R>>;
}
