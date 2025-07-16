/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export const $ThreadUpdate = {
    properties: {
        title: {
            type: 'any-of',
            contains: [{
                type: 'string',
            }, {
                type: 'null',
            }],
        },
        add_participants: {
            type: 'array',
            contains: {
                type: 'string',
            },
        },
    },
} as const;
