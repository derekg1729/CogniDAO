import { BaseError } from "./base-error.js";
import { ErrorName } from "./error-names.js";

export class InvalidParamError extends BaseError {
  constructor(paramName: string) {
    super(`Invalid parameter: ${paramName}`, ErrorName.INVALID_PARAM_ERROR);
  }
}
