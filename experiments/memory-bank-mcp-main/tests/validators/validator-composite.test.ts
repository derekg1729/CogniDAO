import { beforeEach, describe, expect, it } from "vitest";
import { Validator } from "../../src/presentation/protocols/validator.js";
import { ValidatorComposite } from "../../src/validators/validator-composite.js";

interface TestInput {
  field: string;
}

class ValidatorStub implements Validator {
  error: Error | null = null;
  callCount = 0;
  input: any = null;

  validate(input?: any): Error | null {
    this.callCount++;
    this.input = input;
    return this.error;
  }
}

describe("ValidatorComposite", () => {
  let validator1: ValidatorStub;
  let validator2: ValidatorStub;
  let sut: ValidatorComposite;

  beforeEach(() => {
    validator1 = new ValidatorStub();
    validator2 = new ValidatorStub();
    sut = new ValidatorComposite([validator1, validator2]);
  });

  it("should call validate with correct input in all validators", () => {
    const input = { field: "any_value" };
    sut.validate(input);
    expect(validator1.input).toBe(input);
    expect(validator2.input).toBe(input);
  });

  it("should return the first error if any validator fails", () => {
    const error = new Error("validator_error");
    validator1.error = error;

    const result = sut.validate({ field: "any_value" });

    expect(result).toBe(error);
  });

  it("should return the second validator error if the first validator passes", () => {
    const error = new Error("validator_error");
    validator2.error = error;

    const result = sut.validate({ field: "any_value" });

    expect(result).toBe(error);
  });

  it("should return null if all validators pass", () => {
    const result = sut.validate({ field: "any_value" });

    expect(result).toBeNull();
  });

  it("should call validators in the order they were passed to the constructor", () => {
    sut.validate({ field: "any_value" });

    expect(validator1.callCount).toBe(1);
    expect(validator2.callCount).toBe(1);
  });

  it("should stop validating after first error is found", () => {
    validator1.error = new Error("validator_error");

    sut.validate({ field: "any_value" });

    expect(validator1.callCount).toBe(1);
    expect(validator2.callCount).toBe(0);
  });
});
