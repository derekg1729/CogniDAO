import { Validator } from "../../../src/presentation/protocols/index.js";

export class MockValidator<T> implements Validator<T> {
  validate<S extends T>(input: S): null;
  validate(input?: any): Error;
  validate(input?: any): Error | null {
    return null;
  }
}

export const makeValidator = <T>(): Validator<T> => {
  return new MockValidator<T>();
};
