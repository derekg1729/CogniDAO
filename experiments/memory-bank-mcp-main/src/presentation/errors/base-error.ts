import { ErrorName } from "./error-names.js";

export abstract class BaseError extends Error {
  constructor(message: string, name: ErrorName) {
    super(message);
    this.name = name;
  }
}
