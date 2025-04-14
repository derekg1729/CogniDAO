import { describe, expect, it } from "vitest";
import {
  NotFoundError,
  UnexpectedError,
} from "../../../src/presentation/errors/index.js";
import {
  badRequest,
  notFound,
  ok,
  serverError,
} from "../../../src/presentation/helpers/index.js";

describe("HTTP Helpers", () => {
  describe("badRequest", () => {
    it("should return 400 status code and the error", () => {
      const error = new Error("any_error");
      const response = badRequest(error);
      expect(response).toEqual({
        statusCode: 400,
        body: error,
      });
    });
  });

  describe("notFound", () => {
    it("should return 404 status code and the error", () => {
      const response = notFound("any_error");
      expect(response).toEqual({
        statusCode: 404,
        body: new NotFoundError("any_error"),
      });
    });
  });

  describe("serverError", () => {
    it("should return 500 status code and wrap the error in UnexpectedError", () => {
      const error = new Error("any_error");
      const response = serverError(error);
      expect(response).toEqual({
        statusCode: 500,
        body: new UnexpectedError(error),
      });
    });
  });

  describe("ok", () => {
    it("should return 200 status code and the data", () => {
      const data = { name: "any_name" };
      const response = ok(data);
      expect(response).toEqual({
        statusCode: 200,
        body: data,
      });
    });
  });
});
